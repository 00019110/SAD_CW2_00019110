# Conversation with Claude (AI assistant) – SAD CW2, student 00019110

This is the record of the conversation in which the coursework artefacts were produced with Claude Code
(Anthropic's AI coding assistant, model Claude Fable 5.2), running in VS Code on 25–26 November 2026.

**What is included:** the messages the student wrote, the plan the student approved, the assistant's replies
as saved in the session record, and a one-line note for each action the assistant took (commands run, files
written). Short progress notes shown on screen between actions are not all kept in that record.

**What is left out:** the raw output of those actions (file contents, command output, screenshots), the
assistant's private reasoning, and automated system messages. The student's email address and local user
folder paths have been removed. The record ends at the point the transcript was exported.

---

## Student

> these folder is your context CW1 is already done with my group. please plan and give step by step instructions on what we will do complete CW2

<details><summary>8 action(s) by the assistant</summary>

- listed files
- read `Coursework-02-individual-v2 (1).pdf`
- Print the text of the CW1 Word document and list its embedded files
- read `bnso6dfuv.txt`
- started a helper agent: Summarize weeks 6-8 materials
- started a helper agent: Summarize weeks 9-11 materials
- Check which development tools are installed
- asked the student: Which student ID is yours? CW2 is individual and the file must be named SAD_CW2_STUDENTID.docx.; What should the high-fidelity prototype (the executable program, 35 points) be built with? Node 22, Python 3.13 and .NET 9 are installed on this machine.; The submission is a single .docx (no zip), yet the marking scheme deducts 35 points each for missing code and missing video. How do you want to link the code and the screencast from the report?; How should we split the work on the written report (class diagram commentary and the 20-point methodology comparison)? The brief explicitly allows AI for the high-fidelity prototype but says nothing either way about the report text.

</details>

**Student's choice:** Your questions have been answered: "Which student ID is yours? CW2 is individual and the file must be named SAD_CW2_STUDENTID.docx."="00019110", "What should the high-fidelity prototype (the executable program, 35 points) be built with? Node 22, Python 3.13 and .NET 9 are installed on this machine."="Python (Flask + SQLite)", "The submission is a single .docx (no zip), yet the marking scheme deducts 35 points each for missing code and missing video. How do you want to link the code and the screencast from the report?"="GitHub + video link (Recommended)", "How should we split the work on the written report (class diagram commentary and the 20-point methodology comparison)? The brief explicitly allows AI for the high-fidelity prototype but says nothing either way about the report text."="Full draft for me to edit".

<details><summary>2 action(s) by the assistant</summary>

- Search early-week lectures for prototype-fidelity and methodology keywords
- read `SAD-Tutorial-10.pdf`

</details>

### Claude

Lecture review is done; I have everything I need and I'm writing up the plan now.

<details><summary>3 action(s) by the assistant</summary>

- wrote `these-folder-is-your-wild-clarke.md`
- looked up a tool
- presented the plan for approval

</details>

**Student's choice:** The student approved the plan below.

<details><summary>The approved plan</summary>

# SAD CW2 plan — NSP Learning Centre (student 00019110)

## Context

CW2 (60% of the module, individual) continues the CW1 case: the **Teacher Workload, KPI & Retention module for NSP Learning Centre**, integrated with EduTizim. The brief's deadline is **26-11-2026 — tomorrow** — so everything below is sized to finish today, leaving tomorrow morning for your video, review and upload.

What gets marked (100 points, +10 bonus):

| Part | Points | What loses marks |
|---|---|---|
| Low-fidelity prototype | 15 | "Just wireframes" (not linked together): −6 |
| High-fidelity prototype (executable) | 35 | No video: −35. No code: −35 |
| Architecture diagram (packages + classes) | 10 | — |
| Class diagram | 20 | No properties/methods: −8. One relationship type only: −8. Too few classes: −8 |
| Methodology comparison | 20 (+10 for a justified custom methodology) | No Agile: −10. Generic, not case-specific: −10 |

Decisions you made: Python **Flask + SQLite**; code on **GitHub** plus a video link; I write a **full report draft** that you edit.

Findings from the lecture slides that shape the work:
- **Class notation (Tutorial 8):** three compartments (name / properties / methods); class name centred, bold, capitalised; members left-aligned, lowercase first letter; visibility `+ - # ~`; types after a colon (`area:double`); hollow triangle = generalization, dashed hollow triangle = realization, hollow diamond = aggregation, filled diamond = composition, dashed arrow = dependency; multiplicities `1`, `*`, `1..*`, `0..1`.
- **Architecture (Lecture 9, Tutorials 10–11):** the module teaches six styles; **Layered** (Presentation / Business logic / Data access) fits this case. Components are identified as internal or external with provided and required interfaces.
- **Design principles (Lecture 10):** Encapsulate the Change, Single Responsibility, Dependency Inversion — the report will justify the class design with these three.
- **Methodologies (Lectures 1–2, 6–7):** Waterfall/SSDM, Spiral, XP, Scrum, prototyping types (throwaway / evolutionary / incremental). The lecturer's framing: pick a methodology for its "side effects" on your context's problems.
- The slides give **no definition of low vs high fidelity**; the brief itself says lo-fi "can be as simple as a series of drawings linked to each other" in draw.io. That is the standard I'll build to.

## What will exist at the end

```
C:\Users\<user>\Desktop\SAD CW\
├── SAD_CW2_00019110.docx          ← the only file you upload to Intranet
└── SAD_CW2_00019110\              ← becomes the GitHub repository (no lecture PDFs or CW1 in it)
    ├── README.md                   how to run, what each folder is
    ├── hifi-prototype\             Flask app (the executable program)
    ├── lofi-prototype\             clickable draw.io file + exported screen images
    └── diagrams\                   UML .drawio sources + PNG exports
```

## Step 1 — Class model first (me, ~30 min)

One class model drives both the code and the UML diagrams, so the diagrams describe the program that is actually on video. About 30 classes taken from CW1's use cases UC-01–UC-04 and requirements FR-01–FR-05:

- **People:** `User` (abstract) ← `Teacher` ← `MainTeacher`, `SupportTeacher`; `User` ← `Student`, `Administrator`, `HeadSpecialist`, `Director`.
- **Scheduling:** `Group`, `Room`, `ScheduledSession` ← `Lesson`, `SupportSession`.
- **Attendance:** `CheckIn`, `WorkSession`, `LessonRegister` ◆— `RegisterEntry`; interface `AttendanceMethod` realised by `QrCodeMethod` and `ManualConfirmation` (Face ID can be added later without touching existing classes — NFR-05.5, "Encapsulate the Change").
- **Performance:** `KpiWeightSet` ◆— `KpiWeight`, `KpiSnapshot` ◆— `IndicatorScore`, `MonthlyRating`, `Achievement`, `Feedback`; interface `KpiIndicator` realised by the seven indicator classes from UC-04.
- **Retention:** `RiskScore`, `RiskAlert` ◆— `FollowUpAction`, `Circumstance`, `Withdrawal`.
- **Services:** `AttendanceService`, `RegisterService`, `KpiService`, `RiskService`, `WorkloadService`, `NotificationService`.
- **Integration:** interface `EduTizimGateway` realised by `ApiEduTizimGateway` / `ExportFileEduTizimGateway` (NFR-05.3 — the vendor may have no API; Dependency Inversion).
- **Enumerations:** `AttendanceStatus`, `CheckInMethod`, `RiskLevel`, `AlertStatus`, `Subject`, `WithdrawalReason`.

This gives every relationship type the marking scheme asks for: generalization, realization, composition, aggregation (`Group` ◇— `Student`), plain association with multiplicities, and dependency.

## Step 2 — High-fidelity prototype (me, ~3–4 h)

Flask + SQLAlchemy over SQLite, laid out in the same layers as the architecture diagram:

```
hifi-prototype\
├── app.py               start with:  python app.py
├── requirements.txt     Flask, SQLAlchemy, segno (QR images), pytest
├── nsp\presentation\    Flask blueprints + templates (one per screen group)
├── nsp\services\        business rules
├── nsp\domain\          the classes from Step 1
├── nsp\data\            database setup, repositories, seed data
├── nsp\integration\     EduTizimGateway + a seeded stand-in for EduTizim
└── tests\               pytest for the rules below
```

Screens, each tied to a CW1 "Must" requirement:

1. **Sign in / role switch** — Teacher, Student, Administrator, Head Specialist, Director; each sees only its own menu (NFR-01.1).
2. **QR check-in / check-out (UC-01, FR-01)** — a room screen with a real QR code that rotates every 60 s; a scan screen with a "simulate scan" button. Real rules: expired code, wrong room, no lesson scheduled, late after 10 min, duplicate scan, early leave, missing check-out; administrator manual confirmation with a mandatory reason.
3. **Lesson register (UC-02, FR-02)** — pre-filled from scans, four statuses, submit blocked while anyone is "Not scanned", lock on submit, consecutive-absence count, alert raised on the third absence.
4. **Dropout Risk Dashboard (UC-03, FR-05)** — risk level counts, open alerts, dropout rate by subject / group / teacher, filters, student detail with risk factors, assign follow-up, resolve or close as withdrawn.
5. **Teacher KPI Dashboard (UC-04, FR-04)** — ranking with seven weighted indicators, teacher detail with 6-month trend, Head Specialist weight settings (must total 100%) and 0–10 monthly rating, "Partial" / "Provisional" labels.
6. **Workload Report (FR-03)** — planned vs worked hours, overtime, lateness, missing check-outs.
7. *If time allows:* student feedback form, retention dashboard per teacher, acquisition cost by subject.

Seed data: fictional students and teachers matching the centre's size (about 150 students, 15 teachers, three subjects), six months of history, and today's timetable generated around the current time so a lesson is always open for check-in. Two students start at two consecutive absences so the alert fires live on video.

Stated limitation (goes in the report): EduTizim is simulated with seed data because there is no access to the vendor's system; the scan is simulated on one screen.

## Step 3 — Low-fidelity prototype (me, ~1 h)

One draw.io file in sketch (hand-drawn) style, **one page per screen, with clickable hotspots linking the pages** — this is what separates it from "just wireframes". About 11 screens: sign in → teacher home → scan QR → check-in confirmed → lesson register → register submitted / alert raised → director home → dropout risk dashboard → student risk detail and follow-up → teacher KPI dashboard → KPI weight settings. Plus one navigation-map page showing how the screens connect.

In the report: the navigation map, a screenshot of each screen with one line on what it tests, a link to the clickable file, and a short table of what changed between lo-fi and hi-fi and why.

## Step 4 — UML diagrams (me, ~1.5 h)

Drawn in draw.io with the Tutorial 8 notation exactly, exported to PNG for the report:

- **Figure A — Overall architecture.** Layered style: packages `presentation`, `services`, `domain` (sub-packages people, scheduling, attendance, performance, retention), `data`, `integration`, plus EduTizim as an external system. Class names inside each package, dashed dependency arrows between packages, provided/required interfaces at the EduTizim boundary.
- **Figure B — Class diagram: people, scheduling and attendance.** Full properties with visibility and types, methods, multiplicities.
- **Figure C — Class diagram: KPI and retention.** Same level of detail.

Splitting the detailed diagram in two keeps the text readable on an A4 landscape page. To export PNGs I'd install draw.io Desktop (`winget install JGraph.Draw`) — I'll ask before installing; the fallback is you exporting from app.diagrams.net (File → Export as → PNG).

## Step 5 — Report draft (me, ~1.5 h)

`SAD_CW2_00019110.docx`: Arial 12, double-spaced, page numbers, contents page, Westminster-Harvard references, cover table copied from the CW1 layout. Analytical, not descriptive, and short — the brief says concise is not penalised.

1. **Case recap** — half a page linking back to CW1.
2. **Prototypes** — lo-fi (Step 3 content); hi-fi screenshots mapped to use cases, GitHub link, video link, run instructions, limitation note.
3. **UML class diagrams** — the three figures; why Layered; how Encapsulate the Change, SRP and DIP shaped specific classes; a table of each relationship type with the reason it was chosen (for example why `RegisterEntry` is composition but `Group`–`Student` is aggregation).
4. **Development methodology** — Waterfall/SSDM versus Scrum, argued only from NSP facts in CW1:
   - KPI weights are unknown and need tuning (interview Q8) — cannot be fixed up front.
   - EduTizim integration depends on the vendor (NFR-05.3) — the biggest technical risk.
   - Classroom tablets and personal-data law ZRU-547 need up-front planning — where Waterfall helps.
   - The CEO is the single decision-maker; 15 teachers cannot attend daily meetings; no HR or IT department.
   - Monthly rhythm of KPI ratings and mock exams; exam-season pressure.
   - Teachers may resist being monitored — an incremental pilot lowers that risk.
   - How CW1's artefacts are used under each (use cases become the backlog versus a signed-off specification) — this covers the "value of systems analysis and design" part of the brief.

   Then the **custom methodology for the +10**: a risk-first opening iteration from Spiral (prove the EduTizim link with a throwaway prototype), the CW1 requirements catalogue as a fixed baseline, two-week Scrum sprints ordered by MoSCoW with month-end reviews, evolutionary prototyping for KPI weights, a pilot in one subject, and TDD for the KPI and risk calculations from XP. Each element justified by a named NSP constraint.
5. **References** — real, checkable sources only (Royce 1970; Boehm 1988; Schwaber and Sutherland 2020; Beck et al. 2001; a systems analysis textbook; Law ZRU-547). You should confirm each one before submitting.

## Step 6 — Your part (you, ~1.5 h)

1. **Run the app and click through it** once, so the video is fluent.
2. **Record the screencast, 60 seconds maximum**, with your voice explaining it — Win+Shift+R (Snipping Tool) or Win+Alt+R (Game Bar). I'll give you a timed shot list: sign in as teacher → scan → register → alert fires → director's risk dashboard → KPI dashboard. A missing or silent-and-unexplained video is treated as non-submission.
3. **Upload the video** (unlisted YouTube or Google Drive with "anyone with the link") and send me the link.
4. **GitHub:** create a public repository; I prepare the local commits and push only once you confirm. Publishing is not reversible in practice, so do it close to submission.
5. **Read and edit the report in your own words**, check the references, and check WIUT's rules on declaring AI use — the brief allows AI for the hi-fi prototype but is silent on the report text.
6. In Word: right-click the contents page → Update field; confirm the three links open in a private browser window.
7. **Submit `SAD_CW2_00019110.docx`** (not zipped) to "Coursework 2" on the Intranet.

## Verification

- `pytest` passes for check-in rules, absence counting, KPI weighting (including "Partial" redistribution) and alert triggers.
- I start the app and walk every screen end to end in a browser, capturing the report screenshots from the running program.
- Each diagram PNG is opened and checked against the Tutorial 8 notation list and against the code (class and attribute names match).
- The lo-fi file's page links are clicked through in order.
- The .docx is opened to confirm fonts, spacing, page numbers, contents page and that all images are legible.
- Final check against the marking table at the top, line by line.

## Order and timing

Today: Steps 1 → 2 → 3 → 4 → 5 (about 8 hours of my work; the hi-fi app comes first because 35 points and the video depend on it). Tomorrow morning: Step 6. If time runs short, the optional screens in Step 2 item 7 are dropped first; nothing else is optional.

</details>

### Claude

Plan approved — starting with the project folder and environment for the high-fidelity prototype.

<details><summary>4 action(s) by the assistant</summary>

- Create the project folders, a Python virtual environment with Flask, and check for browser, Word and GitHub tools
- wrote `base.py`
- wrote `enums.py`
- wrote `people.py`

</details>

### Claude

Environment is ready and the first domain classes (the user hierarchy and enumerations) are written; continuing with the scheduling, attendance, KPI and retention classes.

<details><summary>9 action(s) by the assistant</summary>

- wrote `scheduling.py`
- wrote `attendance.py`
- wrote `performance.py`
- wrote `retention.py`
- wrote `__init__.py`
- Check that the domain classes map to the database correctly
- wrote `database.py`
- wrote `repositories.py`
- wrote `__init__.py`

</details>

### Claude

Domain classes and the data-access layer are done and verified against SQLite; now writing the business-rule services (attendance, register, risk, KPI, workload).

<details><summary>10 action(s) by the assistant</summary>

- wrote `clock.py`
- wrote `notifications.py`
- wrote `attendance.py`
- wrote `risk.py`
- wrote `register.py`
- wrote `kpi.py`
- wrote `workload.py`
- wrote `retention.py`
- Replace three copies of the retention calculation with one shared function
- wrote `edutizim.py`

</details>

### Claude

The EduTizim stand-in (fictional centre data and a timetable built around the current time) is written. Now the importer and demo-history seeder, then the web screens.

<details><summary>4 action(s) by the assistant</summary>

- wrote `sync.py`
- wrote `seed.py`
- Tidy the demo-data seeder so absence counts and alerts stay consistent, then seed a test database and print the totals
- loaded the skill `dataviz`

</details>

### Claude

Demo data seeds correctly (149 active students, 15 teachers, 9 alerts). I'm now building the web screens; first a quick look at the chart colour reference so the dashboards' charts are readable.

<details><summary>7 action(s) by the assistant</summary>

- Read the chart palette reference
- Make the register service send submitted registers back to EduTizim
- wrote `__init__.py`
- wrote `__init__.py`
- wrote `context.py`
- wrote `auth_controller.py`
- wrote `attendance_controller.py`

</details>

### Claude

Sign-in and attendance controllers are written; continuing with the register, risk, KPI, workload and retention controllers, then the page templates.

<details><summary>6 action(s) by the assistant</summary>

- wrote `register_controller.py`
- wrote `risk_controller.py`
- wrote `kpi_controller.py`
- wrote `workload_controller.py`
- wrote `retention_controller.py`
- wrote `style.css`

</details>

### Claude

Controllers and the stylesheet are in place; now writing the page templates (base layout, then each screen).

<details><summary>11 action(s) by the assistant</summary>

- wrote `base.html`
- wrote `_macros.html`
- wrote `login.html`
- wrote `teacher_today.html`
- wrote `student_today.html`
- wrote `scan.html`
- wrote `scan_result.html`
- wrote `room_display.html`
- wrote `rooms.html`
- wrote `exceptions.html`
- wrote `register.html`

</details>

### Claude

The attendance and register screens are written; now the dashboard templates (director overview, dropout risk, KPI, workload, retention).

<details><summary>10 action(s) by the assistant</summary>

- wrote `overview.html`
- wrote `risk_dashboard.html`
- wrote `risk_student.html`
- wrote `feedback.html`
- wrote `kpi_dashboard.html`
- wrote `kpi_teacher.html`
- wrote `kpi_settings.html`
- wrote `workload.html`
- wrote `retention.html`
- Add the remaining small templates, the app entry point and a smoke test that opens every screen, then run it

</details>

### Claude

The whole app runs: all 10 smoke tests pass, including the full walkthrough (scan → register → alert → dashboard). Now adding rule-level tests, then I'll look at the screens in a browser.

<details><summary>7 action(s) by the assistant</summary>

- Write unit tests for the attendance, register, risk, KPI and workload rules and run them
- wrote `conftest.py`
- wrote `test_attendance.py`
- wrote `test_register.py`
- wrote `test_risk.py`
- wrote `test_kpi.py`
- Run the full test suite

</details>

### Claude

All 47 tests pass (37 rule tests plus the screen walkthroughs). Now starting the app and capturing screenshots in a real browser to check how the screens actually look.

<details><summary>4 action(s) by the assistant</summary>

- Install a browser-automation library for taking screenshots and check the app's port is free
- Start the prototype web app
- wrote `shots.py`
- Walk through the running app in a headless browser and save a screenshot of each screen

</details>

### Claude

The full walkthrough ran in a real browser and produced 27 screenshots. I'm now looking at them to check the screens visually.

<details><summary>15 action(s) by the assistant</summary>

- read `02-teacher-today.png`
- read `10-register-submitted-alerts.png`
- read `20-risk-dashboard.png`
- read `23-kpi-dashboard.png`
- read `24-kpi-teacher.png`
- read `21-risk-student.png`
- read `06-checked-in.png`
- Fix the layout issues seen in the screenshots and re-run the tests
- Stop the running prototype server so it can be restarted with the fixes
- Start the prototype web app again
- Re-capture all screenshots from the restarted app into the project's screenshots folder
- read `23-kpi-dashboard.png`
- read `17-admin-exceptions.png`
- read `25-retention-acquisition.png`
- read `19-director-overview.png`

</details>

### Claude

Screens look right after the fixes (sidebar, KPI table, charts). One small KPI-table tweak left, then the README, then on to the low-fidelity prototype.

<details><summary>6 action(s) by the assistant</summary>

- Simplify the KPI table's last column, add a gitignore, re-run tests
- wrote `README.md`
- wrote `drawio.py`
- wrote `render_drawio.py`
- wrote `make_lofi.py`
- Generate the low-fidelity draw.io file and render every page to an image with the draw.io viewer

</details>

### Claude

The low-fidelity prototype file is generated (16 linked pages) and rendered; checking how the sketched screens look.

<details><summary>5 action(s) by the assistant</summary>

- read `0-navigation-map.png`
- read `6-lesson-register.png`
- read `3-scan-room-qr.png`
- Redraw the navigation map with clean arrows and test that clicking the blue elements really moves between pages
- Fix the link-test script and run it again

</details>

### Claude

Testing the clickable links in the low-fidelity file: the first several clicks navigate; one step in my test script picked the wrong element, so I'm checking the output and tightening the test.

<details><summary>8 action(s) by the assistant</summary>

- Re-run the link click-through test with a more specific target
- Re-render all low-fidelity pages to images
- read `0-navigation-map.png`
- read `11-student-risk-detail-and-follow-up.png`
- read `12-teacher-kpi-dashboard.png`
- wrote `uml.py`
- wrote `make_uml.py`
- Generate the UML draw.io file and render each diagram to an image

</details>

### Claude

The five UML diagrams are generated and rendered. Now reviewing each one visually and fixing layout problems.

<details><summary>7 action(s) by the assistant</summary>

- read `b1-people-and-scheduling.png`
- read `a-architecture.png`
- Fix the architecture diagram's layout problems and re-render
- read `a-architecture.png`
- read `b2-attendance.png`
- read `c1-teacher-kpi.png`
- read `c2-dropout-risk.png`

</details>

### Claude

Four of the five diagrams are clean. Two have notes sitting on top of connector lines and one cramped label; fixing those now.

<details><summary>2 action(s) by the assistant</summary>

- Move the overlapping notes, tidy two connectors and re-render the UML diagrams
- read `c1-teacher-kpi.png`

</details>

### Claude

UML diagrams are done (architecture plus four class diagrams, 46 classes and enumerations, all six relationship types). Now writing the Word report.

<details><summary>2 action(s) by the assistant</summary>

- loaded the skill `anthropic-skills:docx`
- Check the Word-document library is available and install a PDF renderer for checking the report

</details>

### Claude

Tools for building the Word report are ready. Writing the report content now (prototypes, UML commentary, methodology comparison and custom methodology).

<details><summary>2 action(s) by the assistant</summary>

- wrote `make_report.js`
- Correct the report draft for accuracy, add automatic word counting and generate the Word file

</details>

### Claude

The report draft is written; I'm applying a set of accuracy corrections to it (the shell choked on quoting, so I'm running the corrections from a file instead).

<details><summary>14 action(s) by the assistant</summary>

- wrote `patch_report.py`
- Apply the corrections and generate the Word report
- Open the report in Word in the background to fill in the contents page, save it and export a PDF copy for checking
- Turn the exported PDF into contact sheets of page thumbnails for a layout check
- read `sheet-1.png`
- read `sheet-4.png`
- read `sheet-6.png`
- read `sheet-3.png`
- Restart the app, retake all screenshots, stop the app and rebuild the Word report
- Refresh the contents page of the rebuilt report in Word and save it
- read `23-kpi-dashboard.png`
- wrote `VIDEO-SCRIPT.md`
- Run the tests one last time, then create a local git repository and list the files staged for it
- Add a test configuration, confirm the tests pass, and make the first local commit (nothing is pushed)

</details>

### Claude

Everything on my side of the plan is built; what remains is your video, the two links, your edit of the report, and submission.

## What exists now

- **Report:** [SAD_CW2_00019110.docx](SAD_CW2_00019110.docx) — 37 pages, Arial 12, double-spaced, contents page filled in, page numbers, Harvard references. About 3,100 words of body text.
- **Repository folder:** [SAD_CW2_00019110/](SAD_CW2_00019110/) — committed locally, nothing pushed.
  - `hifi-prototype/` — the Flask + SQLite app. All four CW1 use cases work with real rules, plus workload, retention and acquisition cost. 47 automated tests pass, and I walked the full flow in a real browser.
  - `lofi-prototype/` — a draw.io file with a navigation map and 15 sketched screens. I clicked through it in the draw.io viewer and the links do move between pages, so it is not "just wireframes".
  - `diagrams/` — one architecture diagram and four class diagrams (58 classes, interfaces and enumerations, all six relationship types, properties and methods with visibility). An earlier progress note said 46; 58 is the correct count.
- **Video script:** [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md) — a timed 55-second shot list with what to click and say.

## Your steps

1. **Run the app:** in `SAD_CW2_00019110\hifi-prototype` run `.venv\Scripts\python app.py`, open http://127.0.0.1:5000.
2. **Record the screencast** following the script. Press **Reset data** (bottom-left) right before recording: check-in only works within 30 minutes of the app's start.
3. **Upload the video** (unlisted YouTube or Drive with link sharing).
4. **Push to GitHub:** create an empty public repository, then in `SAD_CW2_00019110` run `git remote add origin <your repo URL>` and `git push -u origin main`.
5. **Paste both links** into the report at the yellow placeholders (the GitHub link appears three times, the video link once).
6. **Edit the report into your own words**, then submit the .docx to "Coursework 2".

## Check before you submit

- **AI declaration:** the report says the high-fidelity prototype was built with an AI agent, which the brief allows. It says nothing about the report text, which I drafted. Check WIUT's rules and declare accordingly.
- **Order of the prototypes:** the brief says to produce prototypes first; I actually built the high-fidelity one before the low-fidelity one, so the report describes their purposes without claiming an order.
- **Lecture references:** I cited the slides as "Abduvaliev (2026) Lecture 6 / 9 / 10", assuming the lecturer wrote them. Confirm author and titles.
- **Other references:** Royce, Boehm, Schwaber and Sutherland, Beck and Andres, and Anderson are real, but confirm each against your library's Harvard format.
- **One assumption in the methodology section:** CW1 never says whether the centre has IT staff. The report assumes it does not and labels that as an assumption; correct it if you know otherwise.
- **Visibility symbols:** the diagrams mark fields private or protected as design intent; Python does not enforce it. The report says so.

I did not need to install draw.io Desktop; the diagrams were rendered with the draw.io web viewer.

## Student

> dont site the slides make sure links to github and the app's scripts are available and public give me the github link

<details><summary>1 action(s) by the assistant</summary>

- Check the local repository state, any GitHub accounts already signed in on this machine, and whether the GitHub command-line tool exists

</details>

### Claude

A GitHub account named `00019110` is already signed in on this machine, so I can publish directly. Creating the public repository and pushing now.

<details><summary>3 action(s) by the assistant</summary>

- Confirm the signed-in GitHub account, check the repository name is free, and see whether the report file was edited since I built it
- Check the GitHub account details returned for the signed-in credential
- Clear the expired GitHub sign-in and wait for you to sign in again through the browser window that opens

</details>

### Claude

Signed in. Creating the public repository and pushing.

<details><summary>8 action(s) by the assistant</summary>

- Create the public GitHub repository, switch the commit to GitHub's private no-reply email, and push
- Check, without signing in, that the repository and its code files open publicly
- wrote `check_online.py`
- Open the published low-fidelity prototype in the online draw.io viewer and click through the main flow
- Find every mention of lectures or slides in the repository, the diagrams and the report source
- wrote `patch2.py`
- Apply the citation removals and link insertions, then check nothing referring to lectures or placeholders is left
- Regenerate the diagrams without lecture mentions, publish the update to GitHub and rebuild the report

</details>

### Claude

Diagram update is published and the report is rebuilt with the real links. Now refreshing its contents page and testing every link inside the document.

<details><summary>4 action(s) by the assistant</summary>

- Refresh the report's contents page in Word and count its hyperlinks
- Test every link in the report without signing in, and confirm no slide citations or GitHub placeholders remain
- Read back the two draw.io viewer links from the report exactly as Word stores them
- Confirm both online viewer links work in either encoding and that the published diagrams no longer mention lectures

</details>

### Claude

The repository is public and the report now links to it: **https://github.com/00019110/SAD_CW2_00019110**

## What I did

- **Published the repository.** Your saved GitHub sign-in had expired, so you were asked to sign in again; after that I created the public repository and pushed both prototypes and the diagrams.
- **Removed every slide citation.** The three lecture references and their in-text citations are gone from the report, and the lecture mentions inside the diagram notes are gone too (republished).
- **Put real links in the report.** [SAD_CW2_00019110.docx](SAD_CW2_00019110.docx) now has 32 working hyperlinks, including a new table that links to each part of the code: the start script `app.py`, business rules, domain classes, data access, EduTizim boundary, screens, tests and screenshots.
- **Added one-click viewer links.** The low-fidelity prototype and the UML diagrams open straight in the draw.io web viewer from the report, with nothing to download.

I tested every link in the report without being signed in and all of them open. I also clicked through the published low-fidelity prototype online and the page links work.

## Things you should know

- **One placeholder is left:** the screencast link, highlighted yellow in section 2.2. Paste it once you have recorded and uploaded the video; [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md) has the shot list.
- **One citation was added:** with the slides gone, the single-responsibility and dependency-inversion principles had no source, so I cited Martin (2003), *Agile Software Development: Principles, Patterns, and Practices*. Remove it if you prefer no source there.
- **Your email is not exposed:** the public commits use GitHub's no-reply address for your account instead of your Gmail address.
- **The repository is public now**, so classmates can see it before the deadline.

The report is 38 pages and about 3,100 words of body text.

## Student

> does the video has to be less than 1 minutes long?

### Claude

Yes. The brief says: "You must submit **maximum 1 minute** video recording of your running application along with your code." So 60 seconds is the upper limit, not a target.

Two related lines from the same brief are worth keeping in mind:

- "If you fail to submit a screencast **explaining** the application, it will be considered as non-submission." So it needs your voice (or at least on-screen captions) explaining what is happening, not just silent clicking.
- The marking scheme lists "No video recording: −35 points".

The brief does not say what happens if the video runs over a minute. I would not test it: aim for about 55 seconds, which is what the shot list in [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md) is timed for. If your first take runs long, drop the last optional step and shorten the KPI part rather than speaking faster.

## Student

> I pasted the video here please upload it to github or one drive and include links to everything required

<details><summary>3 action(s) by the assistant</summary>

- Look for the video file you added to the folder
- wrote `mp4info.py`
- Read the video's length and whether it has a sound track

</details>

### Claude

The video is 56 seconds with a sound track, so it is within the limit. Before making a screen recording public I'm glancing at a few frames to make sure it shows only the app.

<details><summary>3 action(s) by the assistant</summary>

- wrote `frames.py`
- Capture six still frames from the video for a quick look
- read `frames.png`

</details>

### Claude

The frames show only the prototype running in the browser, so it is fine to publish. Adding it to the GitHub repository now.

<details><summary>2 action(s) by the assistant</summary>

- Add the video to the repository as screencast.mp4, link it from the README, publish, and check it is reachable without signing in
- Open the video's GitHub page as an anonymous visitor and check that a player appears and the video loads

</details>

### Claude

GitHub's file page does not play MP4s in the browser (it only offers a download), so I'm turning on GitHub Pages for the repository to give the marker a link that plays the video directly.

<details><summary>3 action(s) by the assistant</summary>

- wrote `index.html`
- Publish the video page, correct the README, and switch on GitHub Pages for the repository
- Wait for the GitHub Pages site to go live, then check that the video loads in its player for an anonymous visitor

</details>

### Claude

The page is live and the video plays there. Now putting the video links into the report in place (so any edits you made to the document are kept).

<details><summary>3 action(s) by the assistant</summary>

- Replace the yellow video placeholder in the report with working links, save, and export a PDF copy for checking
- Render the edited paragraph for a visual check and re-test every link in the saved report without signing in
- read `video-para.png`

</details>

### Claude

The video is published and the report now has no placeholders left: every required link is in it and works without signing in.

## Links

- **Screencast (plays in the browser):** https://00019110.github.io/SAD_CW2_00019110/
- **Code repository:** https://github.com/00019110/SAD_CW2_00019110
- **Video file in the repository:** https://github.com/00019110/SAD_CW2_00019110/blob/main/screencast.mp4

## What I did

- **Checked the video first:** 56.3 seconds, with a sound track, and the frames I sampled show only the prototype. It is within the one-minute limit.
- **Uploaded it to GitHub** as `screencast.mp4` in the repository root. I used GitHub, not OneDrive.
- **Turned on GitHub Pages for the repository.** GitHub's normal file page only offers an MP4 as a download, so I added a small page that plays the video and lists the other artefacts. I confirmed the video loads there for an anonymous visitor.
- **Put the links in the report** ([SAD_CW2_00019110.docx](SAD_CW2_00019110.docx)) by editing it in place, so anything you changed in the document is kept. Section 2.2 now links to the screencast page and the video file.

## What the report links to

| Required item | Where in the report |
|---|---|
| Screencast | Section 2.2 |
| High-fidelity code, start script, tests, screenshots | Cover page, section 2.2 and Table 2.2 |
| Low-fidelity prototype (clickable online) and its source | Section 2.1 |
| UML diagrams (full size online) and their source | Section 3 |

I re-tested all 17 distinct link targets in the saved document and each one opens.

## Left for you

- Your recording has a black area on the right of the frame (the recording canvas is wider than your screen). It does not hide anything; re-record only if it bothers you, and I can swap the file.
- Read the report through, adjust the wording to your own, and submit `SAD_CW2_00019110.docx` to "Coursework 2" on the Intranet today.

## Student

> add this conversation's link to the CW file as well then I will submit

<details><summary>1 action(s) by the assistant</summary>

- asked the student: This conversation runs locally in VS Code, so it has no web link I can paste, and I won't invent one. How do you want the conversation referenced in the report?

</details>

**Student's choice:** Your questions have been answered: "This conversation runs locally in VS Code, so it has no web link I can paste, and I won't invent one. How do you want the conversation referenced in the report?"="Publish transcript (Recommended)".

<details><summary>3 action(s) by the assistant</summary>

- Locate this conversation's saved record on disk and see how it is structured
- wrote `export_chat.py`
- Preview which messages the transcript export will contain

</details>

### Claude

The transcript export works. I'm tightening its header so it describes exactly what is and isn't included, then checking it for personal details before publishing.

<details><summary>5 action(s) by the assistant</summary>

- Generate the cleaned transcript and scan it for email addresses, user paths, names and access tokens
- edited `export_chat.py`
- edited `export_chat.py`
- edited `export_chat.py`
- Regenerate the transcript with the corrected header and approved plan, and re-scan it for personal details

</details>
