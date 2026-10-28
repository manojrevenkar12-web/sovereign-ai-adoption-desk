-- Record of the desk. Request handlers run as desk_app and see only the customers in
-- current_setting('desk.customers'); the planner runs as desk_planner and sees everything.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'desk_app') THEN CREATE ROLE desk_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'desk_planner') THEN CREATE ROLE desk_planner NOLOGIN; END IF;
END $$;
GRANT desk_app TO CURRENT_USER;
GRANT desk_planner TO CURRENT_USER;

CREATE TABLE customers (
  id text PRIMARY KEY,
  customer_id text GENERATED ALWAYS AS (id) STORED,
  doc jsonb NOT NULL
);

CREATE TABLE use_cases (
  id text PRIMARY KEY,
  customer_id text NOT NULL REFERENCES customers(id),
  doc jsonb NOT NULL
);

CREATE TABLE approvals (
  id text PRIMARY KEY,
  use_case_id text NOT NULL REFERENCES use_cases(id),
  customer_id text NOT NULL REFERENCES customers(id),
  doc jsonb NOT NULL
);

CREATE TABLE usage_weekly (
  customer_id text NOT NULL REFERENCES customers(id),
  week date NOT NULL,
  department text NOT NULL,
  seats int NOT NULL CHECK (seats >= 0),
  active int NOT NULL CHECK (active >= 0),
  messages int NOT NULL CHECK (messages >= 0),
  PRIMARY KEY (customer_id, week, department)
);

CREATE TABLE events (
  id bigserial PRIMARY KEY,
  customer_id text NOT NULL REFERENCES customers(id),
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  prev_hash text,
  hash text NOT NULL
);
CREATE INDEX events_customer ON events (customer_id, id);

CREATE FUNCTION events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'events are append-only';
END $$;
CREATE TRIGGER events_no_update BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION events_append_only();

CREATE TABLE plans (
  use_case_id text PRIMARY KEY REFERENCES use_cases(id),
  customer_id text NOT NULL REFERENCES customers(id),
  computed_at timestamptz NOT NULL,
  doc jsonb NOT NULL
);

CREATE TABLE customer_views (
  customer_id text PRIMARY KEY REFERENCES customers(id),
  computed_at timestamptz NOT NULL,
  doc jsonb NOT NULL
);

CREATE TABLE pov_runs (
  id bigserial PRIMARY KEY,
  customer_id text NOT NULL REFERENCES customers(id),
  use_case_id text NOT NULL REFERENCES use_cases(id),
  at timestamptz NOT NULL DEFAULT now(),
  doc jsonb NOT NULL
);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','use_cases','approvals','usage_weekly','events','plans','customer_views','pov_runs'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY app_scope ON %I TO desk_app
      USING (customer_id = ANY (string_to_array(current_setting('desk.customers', true), ',')))
      WITH CHECK (customer_id = ANY (string_to_array(current_setting('desk.customers', true), ',')))$p$, t);
    EXECUTE format('CREATE POLICY planner_all ON %I TO desk_planner USING (true) WITH CHECK (true)', t);
    EXECUTE format('GRANT SELECT ON %I TO desk_app, desk_planner', t);
  END LOOP;
END $$;

GRANT INSERT ON events, pov_runs TO desk_app;
GRANT UPDATE (doc) ON use_cases TO desk_app;
GRANT USAGE ON SEQUENCE events_id_seq, pov_runs_id_seq TO desk_app, desk_planner;
GRANT INSERT, UPDATE, DELETE ON customers, use_cases, approvals, usage_weekly, plans, customer_views TO desk_planner;
GRANT INSERT ON events, pov_runs TO desk_planner;

CREATE TABLE schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
