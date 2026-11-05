// Build docs/pitch/deck.pptx from the numbers in docs/pitch/claims.md.
//
//   npm install pptxgenjs@3.12.0          (anywhere; then point NODE_PATH at its node_modules)
//   NODE_PATH=<dir>/node_modules node docs/pitch/build_deck.js [apply_theme.js]
//
// The optional argument is the pptx skill's apply_theme.js, which writes the theme colors
// into the file (pptxgenjs cannot). Every number on a slide or in the notes must be in
// claims.md: run `python docs/pitch/check_numbers.py` after building.

const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = path.join(__dirname, "deck.pptx");
const THEME = {
  name: "pcat evidence",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A41", lt1: "FFFFFF", dk2: "4A5568", lt2: "F4F1EA",
    accent1: "2A9D8F", accent2: "C8553D", accent3: "E9B44C", accent4: "8A96A8",
    accent5: "264653", accent6: "6C9A8B", hlink: "2A9D8F", folHlink: "6C9A8B",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "pcat: reviewed code for AI coding agents";
pres.author = "pcat";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const CHART_FONT = "+mn-lt";
const FOOTER = "pcat · simulated evidence; every number sourced in docs/pitch/claims.md";

// --------------------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 8.8, h: 1.2,
      fontFace: THEME.headFontFace, fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 },
      text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.5, w: 8.8, h: 1.5,
      fontFace: THEME.bodyFontFace, fontSize: 24, color: C.background2, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background2 },
  margin: [0.3, 0.5, 0.45, 0.5],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.25, w: 7.0, h: 0.8,
      fontFace: THEME.headFontFace, fontSize: 28, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 },
      text: "" } },
    { text: { text: FOOTER, options: { x: 0.5, y: 5.22, w: 8.0, h: 0.3, fontSize: 10, color: C.text2,
      fontFace: THEME.bodyFontFace, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.22, w: 0.4, h: 0.3, fontSize: 10, color: HEX.dk2, align: "right" },
});
pres.defineSlideMaster({
  title: "CLOSING_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.25, w: 9.0, h: 0.8,
      fontFace: THEME.headFontFace, fontSize: 28, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 },
      text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.22, w: 0.4, h: 0.3, fontSize: 10, color: HEX.lt2, align: "right" },
});

// --------------------------------------------------------------------------- helpers
function tag(slide, text, name) {
  // The evidence tag: where a slide's numbers come from (the deck's recurring motif).
  slide.addText(text, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.15, x: 7.6, y: 0.4, w: 1.9, h: 0.5,
    fill: { color: C.text1 }, color: C.background1, fontSize: 11, bold: true, align: "center", valign: "middle",
    margin: 2, objectName: name || "evidence tag", isTextBox: true });
}

function caveat(slide, text, y = 4.35, h = 0.75) {
  slide.addText([{ text: "Caveat  ", options: { bold: true } }, { text }], {
    shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 0.5, y, w: 9.0, h,
    fill: { color: C.accent3, transparency: 75 }, color: C.text1, fontSize: 14, valign: "middle",
    margin: [4, 10, 4, 10], objectName: "caveat", isTextBox: true });
}

function card(slide, x, y, w, h, head, body, color, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: C.background1 },
    line: { color: color, width: 1.5 }, objectName: `${name} card` });
  slide.addText(head, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.5, fontSize: 18, bold: true, color: color,
    margin: 0, valign: "top", objectName: `${name} heading`, isTextBox: true });
  slide.addText(body, { x: x + 0.2, y: y + 0.7, w: w - 0.4, h: h - 0.85, fontSize: 15, color: C.text1,
    margin: 0, valign: "top", objectName: `${name} text`, isTextBox: true });
}

function stat(slide, x, y, w, big, label, color, name) {
  slide.addText(big, { x, y, w, h: 0.9, fontSize: 44, bold: true, color, fontFace: THEME.headFontFace,
    margin: 0, valign: "bottom", objectName: `${name} number`, isTextBox: true });
  slide.addText(label, { x, y: y + 0.95, w, h: 0.9, fontSize: 15, color: C.text1, margin: 0, valign: "top",
    objectName: `${name} label`, isTextBox: true });
}

function bars(slide, labels, values, colors, opts) {
  slide.addChart(pres.charts.BAR, [{ name: opts.series, labels, values }], {
    x: opts.x, y: opts.y, w: opts.w, h: opts.h, barDir: opts.dir || "bar", chartColors: colors,
    showTitle: true, title: opts.title, titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: CHART_FONT,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 16, dataLabelFontBold: true,
    dataLabelColor: HEX.dk1, dataLabelFontFace: CHART_FONT, dataLabelFormatCode: opts.format || "0",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 14, catAxisLabelFontFace: CHART_FONT,
    valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: opts.max, valGridLine: { style: "none" },
    catGridLine: { style: "none" }, catAxisLineShow: false, showLegend: false, barGapWidthPct: 60,
    catAxisOrientation: (opts.dir || "bar") === "bar" ? "maxMin" : "minMax",
    objectName: opts.name,
  });
}

// --------------------------------------------------------------------------- slides
pres.addSection({ title: "Opening" });

// 1. Title and promise
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
s.addText("pcat", { placeholder: "title" });
s.addText("Reviewed code for AI coding agents: the reviewed version every time, and a human decision whenever it differs.",
  { placeholder: "body" });
s.addText("Evidence from simulations: open-source apps as stand-in organizations, one model, small samples.",
  { x: 0.6, y: 4.5, w: 8.8, h: 0.5, fontSize: 14, color: C.accent3, margin: 0, objectName: "honesty line",
    isTextBox: true });
s.addNotes("pcat makes the code that AI agents write predictable. A team keeps its reviewed versions of common code " +
  "in a catalog, agents fetch them instead of improvising, and CI checks the result. Everything in this deck comes " +
  "from simulations: three open-source apps stood in for companies, I reviewed the catalogs myself, and it was one " +
  "model. Every number is sourced in claims.md, with its caveat.");

// 2. The problem
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Opening" });
s.addText("Same request, different code", { placeholder: "title" });
tag(s, "v2.1 · lab · 480 samples");
bars(s, ["Same prompt", "Paraphrased", "With a reference"], [15.7, 17.4, 2.0], [HEX.accent4, HEX.accent4, HEX.accent1],
  { series: "Effective versions", x: 0.4, y: 1.15, w: 5.4, h: 3.1, max: 20, format: "0.0",
    title: "Effectively distinct versions in 20 tries", name: "variance chart" });
stat(s, 6.1, 1.2, 3.4, "15.7 of 20", "effectively distinct versions in 20 tries of the same request",
  C.accent2, "variance");
stat(s, 6.1, 2.55, 3.4, "2.0", "with a reference in the prompt", C.accent1, "reference");
caveat(s, "Lab prompts, one model, 8 tasks. The reference was put in the prompt, a perfect lookup.");
s.addNotes("We asked the same agent for the same function 20 times, for 8 common tasks. On average it wrote 15.7 " +
  "effectively distinct versions out of 20, so almost every answer was new code. Paraphrasing the request, which is " +
  "what different engineers do, made it 17.4. When we put a reference implementation in the prompt, it collapsed to " +
  "2.0. This was a lab setup with one model, so treat it as a strong signal, not a law.");

// 3. Why it matters
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Opening" });
s.addText("Why it matters", { placeholder: "title" });
card(s, 0.5, 1.25, 2.85, 2.6, "Reviews repeat",
  "Every new version of an access check, a token helper or a retry loop is new code someone has to review.",
  C.accent5, "reviews");
card(s, 3.575, 1.25, 2.85, 2.6, "Consistency is luck",
  "What you get depends on who asked and how they worded it, not on what your team decided.", C.accent5,
  "consistency");
card(s, 6.65, 1.25, 2.85, 2.6, "Flaws can spread",
  "Inside a repository agents copy what is nearby. A weak version that lands becomes the next example.",
  C.accent2, "flaws");
s.addText("Rules files and style guides steer the model. Nothing checks what it actually wrote.", {
  x: 0.5, y: 4.15, w: 9.0, h: 0.7, fontSize: 20, italic: true, color: C.text1, fontFace: THEME.headFontFace,
  margin: 0, valign: "middle", objectName: "gap statement", isTextBox: true });
s.addNotes("Why should a head of engineering care? Three reasons. Reviewers keep re-reading the same kinds of code. " +
  "Consistency depends on luck. And in our real-app runs, agents copied whatever code sat next to the work, which is " +
  "good when that code is right and bad when it is not. Rules files tell the model what to do, but nobody checks the " +
  "output against what reviewers decided.");

pres.addSection({ title: "What pcat is" });

// 4. What pcat is
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "What pcat is" });
s.addText("What pcat is", { placeholder: "title" });
const boxes = [
  ["Catalog", "Reviewed patterns from your own code, with guards: what reviewers care about. Approved by pull request.", C.accent5],
  ["MCP server", "Agents search the catalog, fetch the reviewed version and check their code against it.", C.accent1],
  ["CI linter", "Compares marked code with its pattern. A broken guard fails the pull request until a person decides.", C.accent2],
];
boxes.forEach(([head, body, color], i) => {
  const x = 0.5 + i * 3.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.7, h: 2.55, rectRadius: 0.12, fill: { color },
    objectName: `${head} box` });
  s.addText(head, { x: x + 0.2, y: 1.45, w: 2.3, h: 0.5, fontSize: 20, bold: true, color: C.background1, margin: 0,
    objectName: `${head} heading`, isTextBox: true });
  s.addText(body, { x: x + 0.2, y: 2.0, w: 2.3, h: 1.75, fontSize: 15, color: C.background1, margin: 0,
    valign: "top", objectName: `${head} text`, isTextBox: true });
  if (i < 2) {
    s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.76, y: 2.38, w: 0.34, h: 0.4, fill: { color: C.text2 },
      objectName: `arrow ${i}` });
  }
});
s.addText([
  { text: "The agent marks what it used:  ", options: { color: C.text1 } },
  { text: "# pcat: auth.password.pbkdf2@v1", options: { fontFace: "Courier New", bold: true, color: C.accent5 } },
], { x: 0.5, y: 4.1, w: 9.0, h: 0.5, fontSize: 16, margin: 0, objectName: "marker line", isTextBox: true });
s.addText("Engineers review a pattern once; agents reuse it; CI checks the result.", { x: 0.5, y: 4.6, w: 9.0,
  h: 0.45, fontSize: 16, italic: true, color: C.text2, margin: 0, objectName: "summary line", isTextBox: true });
s.addNotes("pcat has three parts. A catalog of reviewed patterns that your engineers take from your own code and " +
  "approve through ordinary pull requests; each one lists guards, the properties a reviewer cares about. An MCP " +
  "server, so an agent like Claude Code can search the catalog, fetch the reviewed version and check its code. And a " +
  "CI linter that compares marked code with its pattern. The marker is a one-line comment the agent writes above the " +
  "function.");

// 5. How it works in a pull request
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "What pcat is" });
s.addText("How it works in a pull request", { placeholder: "title" });
const steps = [
  ["Marker", ["# pcat:", "auth.password.", "pbkdf2@v1"], "the agent says which pattern it used", C.accent5],
  ["Guard", ["must_call:", "hmac.", "compare_digest"], "the reviewer's rule, kept in the pattern", C.accent5],
  ["Deviation", ["verify_password", "no longer calls", "compare_digest"], "high: the pull request fails", C.accent2],
  ["Human decision", ["# pcat-allow:", "PC100 #e96d53e0", "-- reason"], "a proposal until an approver confirms it",
    C.accent3],
];
steps.forEach(([head, code, note, color], i) => {
  const x = 0.5 + i * 2.3;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.25, w: 2.05, h: 3.0, rectRadius: 0.12,
    fill: { color: C.background1 }, line: { color, width: 2 }, objectName: `${head} step` });
  s.addText(head, { x: x + 0.15, y: 1.35, w: 1.75, h: 0.5, fontSize: 18, bold: true, color, margin: 0,
    objectName: `${head} heading`, isTextBox: true });
  s.addText(code.map((t, j) => ({ text: t, options: { breakLine: j < code.length - 1 } })), {
    x: x + 0.15, y: 1.9, w: 1.75, h: 1.1, fontSize: 13, fontFace: "Courier New", color: C.text1,
    margin: 0, valign: "top", objectName: `${head} code`, isTextBox: true });
  s.addText(note, { x: x + 0.15, y: 3.15, w: 1.75, h: 1.0, fontSize: 15, color: C.text2, margin: 0, valign: "top",
    objectName: `${head} note`, isTextBox: true });
  if (i < 3) {
    s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.07, y: 2.55, w: 0.21, h: 0.35, fill: { color: C.text2 },
      objectName: `step arrow ${i}` });
  }
});
s.addText("Tests would still pass: == gives the same answer. The guard catches the property the reviewer cared about.",
  { x: 0.5, y: 4.4, w: 9.0, h: 0.6, fontSize: 15, italic: true, color: C.text1, margin: 0, valign: "middle",
    objectName: "why guards", isTextBox: true });
s.addNotes("Here is the flow on a real example. The agent writes the password helpers from the catalog and marks them. " +
  "The pattern has a guard: verify_password must use a constant-time comparison. Someone changes it to a plain " +
  "equals. The tests still pass, but the linter fails the pull request with one sentence a reviewer can act on. If the " +
  "change is intended, the author or the agent adds an approval line with the function's hash and a reason. That is " +
  "only a proposal: the check stays red until someone on the approvers list confirms it on the pull request.");

pres.addSection({ title: "Results" });

// 6. Result: first-time code in real apps
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("First-time code: the catalog decides", { placeholder: "title" });
tag(s, "v5 · 3 apps · 144 runs");
bars(s, ["Without pcat", "With pcat"], [2, 12], [HEX.accent4, HEX.accent1],
  { series: "Runs", x: 0.4, y: 1.15, w: 5.0, h: 3.05, max: 14, dir: "col",
    title: "Reproduced the house function, of 12 runs", name: "first-time chart" });
s.addText([
  { text: "On the 4 tasks where the function existed nowhere else in the repo, agents with pcat wrote the house " +
    "version 12/12 times; without it, 2/12.", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Where similar code sits nearby, agents copy it with or without pcat (similarity 1.00 in both).",
    options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "With pcat: searched 71/72, right pattern 54/54, forced onto unrelated work 0/36." },
], { x: 5.7, y: 1.2, w: 3.8, h: 3.0, fontSize: 15, color: C.text1, margin: 0, valign: "top",
  objectName: "first-time findings", isTextBox: true });
caveat(s, "Open-source apps as stand-in organizations; catalogs reviewed by the builder; 3 samples per task; one model.");
s.addNotes("This is the closest we got to real use: three open-source web apps, each treated as its own company with " +
  "its own catalog, and agents working inside the repository on short requests. The honest headline: where similar " +
  "code already exists in the repo, agents copy it anyway, with or without pcat. The catalog's value is for code the " +
  "repo does not have yet. On the 4 tasks like that, agents with pcat wrote the house version 12 out of 12 times, and " +
  "without it 2 out of 12. That rests on 4 tasks and 3 samples each, with catalogs I reviewed.");

// 7. Result: regressions become decisions
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Silent regressions become decisions", { placeholder: "title" });
tag(s, "v4.1 rules · v5 · v5.1");
stat(s, 0.5, 1.15, 2.8, "20 of 60", "lab runs broke a guarded property of the reviewed pattern", C.accent2, "broke");
stat(s, 3.6, 1.15, 2.8, "20 of 20", "flagged, each with a hashed approval proposal for a person to confirm", C.accent3,
  "flagged");
stat(s, 6.7, 1.15, 2.8, "0", "went through without a human decision", C.accent1, "uncovered");
s.addShape(pres.shapes.LINE, { x: 0.5, y: 3.15, w: 9.0, h: 0, line: { color: C.accent4, width: 0.75 },
  objectName: "divider" });
s.addText([
  { text: "0/72 ", options: { bold: true, color: C.accent1, fontSize: 26, fontFace: THEME.headFontFace } },
  { text: "With markers, no correct code failed CI in 144 runs inside the three apps (an earlier linter version " +
    "failed 5, all explained and fixed).", options: { color: C.text1 } },
], { x: 0.5, y: 3.25, w: 9.0, h: 0.9, fontSize: 15, margin: 0, valign: "middle", objectName: "quiet ci",
  isTextBox: true });
caveat(s, "One rule set. The lab requests asked for the deviation (\"not on 4xx errors\"; 429 is a 4xx). " +
  "Agents write the proposals; a human must still read them.");
s.addNotes("Under one rule set, 20 of 60 lab runs produced code that broke a guarded property, in this case no longer " +
  "retrying on HTTP 429. Every one was flagged, and every one came with a hashed approval proposal that keeps CI red " +
  "until a person confirms it. None went through on its own. Note that the requests asked for this: they said do not " +
  "retry on 4xx errors, and 429 is one. That is exactly the kind of conflict a human should decide. And on correct " +
  "code in the real apps, the check failed none of the 144 runs.");

// 8. Result: a flawed neighbour (supporting only)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Supporting: a flawed neighbour", { placeholder: "title" });
tag(s, "v5.2 · 108 runs · small");
bars(s, ["Without the catalog", "With the catalog"], [3, 0], [HEX.accent2, HEX.accent1],
  { series: "Runs", x: 0.4, y: 1.15, w: 5.0, h: 3.05, max: 6, dir: "col",
    title: "Runs that inherited a planted flaw, of 54", name: "neighbour chart" });
s.addText([
  { text: "All 3 were in the 2 tasks where the flawed function was the obvious stand-in: 3/6 vs 0/6.",
    options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "51/54 runs without the catalog did not copy the flaw.", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Default CI caught 0/3: copied code has no marker." },
], { x: 5.7, y: 1.2, w: 3.8, h: 3.0, fontSize: 15, color: C.text1, margin: 0, valign: "top",
  objectName: "neighbour findings", isTextBox: true });
caveat(s, "We planted the flaws; 6 runs carry the effect; self-reviewed catalogs; one model. Supporting only.");
s.addNotes("We planted one flawed function next to the work, for example a rate limiter keyed on the wrong IP. " +
  "Without the catalog, 3 of 54 runs inherited the flaw; with it, none did. But be careful with this one: all 3 were " +
  "in the 2 tasks where the flawed function was the obvious stand-in, so 6 runs carry the effect, and we wrote the " +
  "flaws ourselves. Most runs did not copy the flaw even without the catalog. Also, default CI did not catch the " +
  "copies, because copied code has no marker.");

pres.addSection({ title: "Limits and next steps" });

// 9. What it is not
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Limits and next steps" });
s.addText("What pcat is not", { placeholder: "title" });
card(s, 0.5, 1.25, 2.85, 2.35, "Not a style guide",
  "It checks the properties reviewers care about (guards), not formatting or naming.", C.accent5, "style");
card(s, 3.575, 1.25, 2.85, 2.35, "Not a code generator",
  "The agent still writes the code. pcat supplies reviewed examples and checks the result.", C.accent5, "generator");
card(s, 6.65, 1.25, 2.85, 2.35, "Not proven at scale",
  "No real team has used it yet: 3 open-source apps, one model, small samples.", C.accent2, "scale");
s.addText([
  { text: "Noisy where unmarked: ", options: { bold: true } },
  { text: "of 90 sampled findings on code nobody marked, 75 were false positives and 0 true. They stay advisory, " +
    "out of required checks." },
], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 0.5, y: 3.85, w: 9.0, h: 1.0,
  fill: { color: C.accent3, transparency: 75 }, color: C.text1, fontSize: 15, valign: "middle",
  margin: [4, 10, 4, 10], objectName: "noise card", isTextBox: true });
s.addNotes("To be clear about what this is not. It is not a style guide: it does not care about names or formatting. " +
  "It is not a code generator: the agent still writes the code. And it is not proven at scale: everything so far is " +
  "simulated. One more limit: when the linter guesses that unmarked code came from a pattern, it is usually wrong, " +
  "75 of 90 sampled findings were false positives, so those findings never fail a build.");

// 10. How to try it
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Limits and next steps" });
s.addText("How to try it", { placeholder: "title" });
s.addText([
  { text: "pipx install \"pcat[mcp] @ git+…/pcat\"", options: { breakLine: true } },
  { text: " ", options: { breakLine: true } },
  { text: "cd your-repo", options: { breakLine: true } },
  { text: "pcat init --starter          # dry run", options: { breakLine: true } },
  { text: "pcat init --starter --apply", options: { breakLine: true } },
  { text: " ", options: { breakLine: true } },
  { text: "pcat audit . --out pcat-audit" },
], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 0.5, y: 1.25, w: 5.0, h: 3.1,
  fill: { color: C.text1 }, color: C.background1, fontFace: "Courier New", fontSize: 14, valign: "middle",
  margin: [6, 14, 6, 14], objectName: "commands", isTextBox: true });
s.addText([
  { text: "About 30 minutes with docs/getting-started.md", options: { bullet: true, breakLine: true } },
  { text: "7 starter patterns; add your own from .pcat/candidates.md", options: { bullet: true, breakLine: true } },
  { text: "Claude Code finds the server through .mcp.json", options: { bullet: true, breakLine: true } },
  { text: "Two pull-request checks; the audit is one-time, never a gate", options: { bullet: true } },
], { x: 5.8, y: 1.25, w: 3.7, h: 3.1, fontSize: 16, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 10,
  objectName: "try it points", isTextBox: true });
s.addText("Python only, 3.11 or newer. Installs from git today (0.1.0).", { x: 0.5, y: 4.55, w: 9.0, h: 0.45,
  fontSize: 14, color: C.text2, margin: 0, objectName: "requirements", isTextBox: true });
s.addNotes("Trying it takes about 30 minutes with the getting-started guide. pcat init shows every file it would " +
  "create, then sets up the catalog with 7 starter patterns, the Claude Code configuration and two pull-request " +
  "checks. The guide walks through turning one of your own functions into a reviewed pattern, and seeing a deviation " +
  "on a pull request. The audit is a one-time report on existing code, for a person to read.");

// 11. What's next: the pilot
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Limits and next steps" });
s.addText("Next: a 4-week pilot with a real team", { placeholder: "title" });
const weeks = [
  ["Before", "Agree success criteria; baseline from past pull requests"],
  ["Week 1", "pcat init, audit, first patterns from the team's own code"],
  ["Week 2", "Normal work with Claude Code; checks required"],
  ["Week 3", "Fix patterns agents missed or misused"],
  ["Week 4", "Measure, interview, write up"],
];
weeks.forEach(([head, body], i) => {
  const x = 0.5 + i * 1.84;
  s.addShape(pres.shapes.OVAL, { x: x + 0.62, y: 1.25, w: 0.36, h: 0.36, fill: { color: i === 0 ? C.accent4 : C.accent1 },
    objectName: `${head} dot` });
  s.addText(head, { x, y: 1.7, w: 1.6, h: 0.4, fontSize: 16, bold: true, color: C.text1, align: "center", margin: 0,
    objectName: `${head} label`, isTextBox: true });
  s.addText(body, { x, y: 2.1, w: 1.6, h: 1.1, fontSize: 13, color: C.text2, align: "center", margin: 0, valign: "top",
    objectName: `${head} text`, isTextBox: true });
});
s.addShape(pres.shapes.LINE, { x: 1.3, y: 1.43, w: 7.36, h: 0, line: { color: C.accent4, width: 1 },
  objectName: "timeline" });
s.addText([
  { text: "It measures: ", options: { bold: true } },
  { text: "how often agents fetch the pattern; whether first-time code matches it; that every high deviation gets a " +
    "human decision; false CI failures per week; time to write a pattern; review effort (a hypothesis)." },
], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 0.5, y: 3.4, w: 9.0, h: 1.45,
  fill: { color: C.background1 }, line: { color: C.accent1, width: 1.5 }, color: C.text1, fontSize: 15,
  valign: "middle", margin: [6, 12, 6, 12], objectName: "pilot metrics", isTextBox: true });
s.addNotes("The next step is a pilot with one real team for 4 weeks, on one Python repository where engineers already " +
  "use Claude Code. The team provides a pattern owner and a few approvers. We agree the success criteria before we " +
  "start and report the results even if they miss. The pilot measures the same things as the simulations, on real " +
  "pull requests, plus the two things we could not simulate: what patterns cost to write, and whether reviews get " +
  "easier.");

pres.addSection({ title: "Appendix" });

// 12. Appendix: method and caveats
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Appendix" });
s.addText("Appendix: method and caveats", { placeholder: "title" });
const hdr = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk1 } } });
s.addTable([
  [hdr("Study"), hdr("Setup"), hdr("Size"), hdr("Main caveat")],
  ["Variance (v2.1)", "Same request, with and without a reference", "480 samples, 8 tasks", "Lab prompts"],
  ["Real apps (v5)", "3 open-source apps as stand-in orgs", "144 runs", "4 tasks carry the effect"],
  ["Gate (v4.1, v5)", "Lab requests under the v4.1 rules", "60 runs", "Requests asked for it"],
  ["Linter (v5.1)", "Real-app runs re-scored, no new runs", "144 runs", "No general error rate"],
  ["Neighbour (v5.2)", "Flawed function planted next to work", "108 runs", "6 runs carry the effect"],
], { x: 0.5, y: 1.2, w: 9.0, colW: [1.6, 3.4, 1.8, 2.2], fontSize: 13, color: HEX.dk1, valign: "middle",
  border: { type: "solid", pt: 0.5, color: HEX.accent4 }, fill: { color: HEX.lt1 }, rowH: 0.42, margin: 3,
  objectName: "method table" });
s.addText("Everywhere: one model (claude-sonnet-5-5 through Claude Code); catalogs picked and reviewed by the builder, " +
  "not by app maintainers; costs are the CLI's own estimates. Sources and caveats for every number: " +
  "docs/pitch/claims.md.", { x: 0.5, y: 4.0, w: 9.0, h: 1.0, fontSize: 14, color: C.text1, margin: 0, valign: "top",
  objectName: "global caveats", isTextBox: true });
s.addNotes("For anyone who wants the method. Five studies, all simulated, each with its own main caveat. Three things " +
  "hold for all of them: one model through Claude Code, catalogs I picked and reviewed myself, and small samples. " +
  "claims.md lists every number with its source file and section.");

// --------------------------------------------------------------------------- write
(async () => {
  await pres.writeFile({ fileName: OUT });
  const themeScript = process.argv[2];
  if (themeScript) {
    const { applyTheme } = require(path.resolve(themeScript));
    await applyTheme(OUT, THEME);
  }
  console.log(`wrote ${OUT}`);
})();
