import type { AiActClass } from "../api/types";
import { CLASS_LABEL } from "../format";
import { folderVar } from "../../theme/tokens";
import s from "./ui.module.css";

/** The coloured folder tab: how this file must be handled under the AI Act. */
export function ClassMark({ klass, stopped = false }: { klass: AiActClass; stopped?: boolean }) {
  return (
    <span
      className={`${s.classMark} ${stopped ? s.stopped : ""}`}
      style={{ ["--tab" as string]: folderVar[klass] }}
      title={`AI Act: ${CLASS_LABEL[klass]}${stopped ? " (stopped)" : ""}`}
    >
      {CLASS_LABEL[klass]}
    </span>
  );
}
