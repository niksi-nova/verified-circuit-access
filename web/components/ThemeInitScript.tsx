import { THEME_INIT_SOURCE } from "@/lib/theme";

/** Server component: sets data-theme before paint to avoid a flash of
 * the wrong theme. The literal script text is duplicated from
 * THEME_INIT_SOURCE on purpose (dangerouslySetInnerHTML needs a plain
 * string, not an import reference). */
export function ThemeInitScript() {
  return <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SOURCE }} />;
}
