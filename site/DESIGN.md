# Design: the study console (Direction B)

The site is a console for one study: it tells you the next thing to do, shows what is running on
your laptop and how the site knows it, and puts reading and exercises in a calm column. This file
is the reference for how it looks. The tokens live in `src/styles.css`. `tests/design.test.ts`
checks their contrast, and `e2e/design.spec.ts` checks the layout rules and runs axe. The
screenshots are in `docs/screenshots/` (see its README).

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F6F7F9` | `#111419` | page background, main column |
| `--surface` | `#FFFFFF` | `#181C23` | rail, top bar, notices, dialogs, code cells |
| `--text` | `#1C2330` | `#E7EAEF` | text |
| `--text-2` | `#3F4855` | `#BCC3CD` | secondary text |
| `--muted` | `#5A6474` | `#9AA3B0` | muted text, axis labels |
| `--rule` | `#DDE1E7` | `#2B313B` | 1px rules between groups |
| `--rule-faint` | `#E7EAEE` | `#232830` | rules between table rows, gridlines |
| `--control` | `#C9CFD8` | `#48515E` | borders of inputs and secondary buttons |
| `--blue` | `#1F5FBF` | `#7AA7F0` | links, actions, forecasts, the current step |
| `--blue-hover` | `#174A96` | `#9DBDF4` | hover of links |
| `--btn` / `--btn-hover` | `#1F5FBF` / `#174A96` | `#2F6AC7` / `#3A74D6` | primary button (white text) |
| `--tint` | `#E6EDF8` | `#1C2B42` | the current phase or step, the chosen answer |
| `--ring` | `#A3ABB6` | `#6B7482` | pending status ring |
| `--observed` | `#1C2330` | `#D9DEE5` | observed data (graphite) and the done glyph |
| `--forecast` | `#1F5FBF` | `#7AA7F0` | forecasts (always dashed) |
| `--unseen` | `#ECEEF3` | `#1E232B` | the "not yet seen" part of a chart |
| `--code-bg` | `#F0F2F5` | `#1F242C` | code |
| `--success`, `--danger` (+ `-tint`) | `#1E6E46`, `#B42318` | `#7CC9A0`, `#F4A097` | verdicts and errors only, always with a word or ✓/✗ |

The dark theme was derived by hand from the light one rather than inverted. Every text token
passes WCAG AA (4.5:1) on the background, the surface and the tint in both themes. The primary
button is `#2F6AC7` in dark mode, because white on the light-theme blue brightened for dark
backgrounds would fail. The two additions to the brief are the success and danger colours: a
failed sync or a failed check needs a colour that reads as an error. They are used only with a
word.

**Exception, documented:** the pending ring `#A3ABB6` has a contrast of 2.32:1 on white, below
the 3:1 that WCAG asks of meaningful graphics. It is kept because the brief specifies it, and it
never carries meaning alone: every glyph sits next to a status word or line, and screen readers
get the word, not the glyph. The dark ring reaches 3.6:1.

The theme follows the system. Account → Appearance can force light or dark (`data-theme` on
`<html>`, remembered in `localStorage`).

## Type

- **IBM Plex Sans** (400/500/600/700) for the interface: 15px base, 14px in tables and
  secondary text, 12–13px for metadata. H1 is 30px/600 (26px below 860px), H2 18px/600.
- **Source Serif 4** for lesson reading: 19px, line height 1.7, measure 65ch.
- **IBM Plex Mono** for commands and code, 13px.
- Numbers in tables, counts and dates use tabular numerals.
- All three fonts are self-hosted from the `@fontsource` packages (latin subsets only, imported
  in `src/main.tsx`), so the CSP keeps `font-src 'self'`. No CDN.

## Shape

The radius is 6px everywhere. There are no shadows and no card grids. Groups are separated by
spacing and 1px rules: 48px between sections on Home, a rule between table rows and between
commands. The only boxed elements are notices (a 3px left rule gives their kind), code cells,
dialogs and the primary button.

## Data semantics

- **Observed** values are a solid graphite line. On a chart question, what happened continues
  the history in the same style.
- **Forecasts** are a blue dashed line.
- Colour is never the only signal. Each line also has a style and a direct label at its end
  ("Your forecast", "What happened") or in a legend. On Results, every model line is dashed and
  labelled. The selected model (a legend button) is blue and the others grey, and the reference
  (zero) is solid graphite. In the contamination chart, foundation models are blue filled dots
  and placebo pairs are graphite hollow squares.
- The Results matrix keeps its diverging bins (blue = model better, warm = model worse, grey
  midpoint). Every cell also prints its number, plus ★ and ● marks.

## Layout

- **Top bar**, 56px: product name, Home · Lessons · Review · Results · Notes, the save state
  ("Progress saved", "Saved in this browser", "Saving…", "Sync failed") and the account button.
  On a lesson page the bar shows only "Back to Home" and the save state. Below 860px the
  sections move into a Menu button.
- **Rail**, 290px, white. On Home, Lessons, Review, Notes, Results and task pages it is *Your
  path*. It shows the phases with a glyph and one line each, the current phase tinted, "N of M
  steps", and links to every step, the tour and research status. On a lesson it shows the
  lesson's steps (glyph each, the current one tinted) under the phase context and lesson title.
- **Glyphs** (16px): done = filled graphite circle with a check; running = blue dashed ring;
  current = blue ring with a dot; pending = grey ring.
- **Main**, grey, content up to 760px (1080px on Results and Research status). Home adds a
  250px *Today* column on the right.
- **Home**, in order:
  1. The next action: context line, H1 "Next: …", why, one primary button, time.
  2. "The study on your laptop": each stage, what it produces, its status and how the site
     knows. The evidence is *Detected*, *Verified from output* or *Self-reported*. Stages that
     share one fact, such as four stages all running as one self-reported command, show it once
     across their rows. "It has finished" opens the paste check in a dialog.
  3. "Models under test", generated from `study.json`: config + contamination buffer, written by
     `make publish-results`.
  4. *Today*: flashcards due, lessons done and learning time, whether results are synthetic, and
     where progress is saved.
- **Lesson**: "Step N of M", H1, serif text, figures and exercises. There is exactly one primary
  Next: the next step, or on the last step the next step on your path (`nextAction()`).

### Responsive

- Below 1200px, *Today* moves below the main column.
- Below 860px, the rail becomes a disclosure button ("Your path: Phase 3 of 8, Foundations";
  "Lesson 02: step 2 of 8" on a lesson). Tables stack into label/value rows. Wide tables with
  many numeric columns (the Results matrix) scroll inside their own box.
- At 390px nothing scrolls sideways, and controls are at least 44px tall. On Home the primary
  action is visible without scrolling. Charts lay out at the width they are shown at, so their
  text stays 12px.

## Controls and states

- Native controls throughout: a predict question is a `fieldset` with a `legend` and radio
  buttons, the OS choice is a tab list, and the theme choice is a radio group.
- **Predict**:
  1. The chosen answer gets the tint and a "Your forecast" tag. On a chart question it is drawn
     as a blue dashed line.
  2. "Check what happened" is disabled until an answer is chosen, and the button says why.
  3. On check, the realised path draws in as a solid graphite line (450ms; instant with reduced
     motion). The tags update to "What happened" and "Your forecast, and what happened".
  4. An `aria-live` result gives the verdict, what happened, the explanation, and the tally over
     all similar shocks, with Continue and Try again.
  5. Try again lets you explore. The first checked answer stays the stored one.
- **Loading**: a line in `index.html` until the app starts, and "Loading results…" on Results.
- **Errors**:
  - a failed sync shows a notice with *Try again*;
  - a failed save in the browser explains itself and points to the export;
  - a failed Results fetch shows *Try again*;
  - Python that fails to start offers *Try again*;
  - a failed start shows the boot message.
- **Empty**: nothing due in Review, no sessions in Notes, no series for a Results selection, no
  `study.json` in the build.
- Motion is quick (120ms colour changes, 450ms line draw) and switched off under
  `prefers-reduced-motion`.
