# SAD CW2 – NSP Learning Centre: Teacher Workload, KPI & Retention module

Systems Analysis and Design (6BUIS026C), Coursework 2, student ID 00019110.

This repository holds the artefacts referenced in the report `SAD_CW2_00019110.docx`.

| Folder / file | What it is |
|---|---|
| [`screencast.mp4`](screencast.mp4) | **Screencast** – 56-second narrated recording of the high-fidelity prototype running. [Watch it in the browser](https://00019110.github.io/SAD_CW2_00019110/) |
| [`hifi-prototype/`](hifi-prototype/) | **High-fidelity prototype** – an executable web application (Python, Flask, SQLite) |
| [`lofi-prototype/`](lofi-prototype/) | **Low-fidelity prototype** – a clickable draw.io file, one sketched screen per page, linked together |
| [`diagrams/`](diagrams/) | **UML class diagrams** – draw.io sources and PNG exports (architecture + four class diagrams) |

## The case

NSP Learning Centre (Urgench) manages students, groups and payments in EduTizim, a commercial CRM.
Coursework 1 found three gaps: teacher attendance is kept by hand in Excel, teacher evaluation has no
standard KPI, and nobody is warned when a student is about to drop out. The proposed module adds QR
attendance, a teacher KPI dashboard and dropout-risk monitoring on top of EduTizim.

## Running the high-fidelity prototype

Requires Python 3.11 or newer.

```
cd hifi-prototype
python -m venv .venv
.venv\Scripts\activate          (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and choose an account on the sign-in page. Each start rebuilds the demo
database, with today's timetable placed around the current time so a lesson is always open for check-in.

Run the tests with `python -m pytest` (47 tests).

### What it does

| Screen | Use case / requirement from CW1 |
|---|---|
| Scan room QR, room QR screen, manual confirmation, missing check-outs | UC-01 Check In / Out via QR Code (FR-01) |
| Lesson register | UC-02 Record Student Attendance (FR-02) |
| Dropout Risk Dashboard, student detail, follow-up, withdrawal | UC-03 View Dropout Risk Dashboard (FR-05) |
| Teacher KPI Dashboard, teacher detail, weights and ratings | UC-04 View Teacher KPI Dashboard (FR-04) |
| Workload Report | View Workload Report (FR-03) |
| Retention & acquisition cost, student feedback | FR-05.6, FR-05.7, FR-04.4 |

### How the code is organised

The code follows the layered architecture shown in the report's architecture diagram.

```
hifi-prototype/nsp/
  presentation/   Flask controllers and HTML templates – no business rules
  services/       business rules: attendance, register, risk, KPI, workload, retention
  domain/         the classes in the UML class diagrams
  data/           repositories (all database queries) and demo data
  integration/    EduTizimGateway – the boundary with the centre's existing CRM
```

### Limits of the prototype

- EduTizim is simulated. The prototype has no access to the vendor's system, so `DemoEduTizimGateway`
  supplies fictional students, teachers, groups and a timetable. All names and figures are invented.
- The QR scan is simulated on one screen: the scan page reads the code currently shown on the chosen
  room's screen. The room screen does show a real rotating code (`python app.py --lan` lets a phone
  on the same network scan it).
- Sign-in has no password, because the real module would reuse EduTizim accounts.
- The "Demo controls" in the sidebar (clock forward, reset data) exist only so a 90-minute lesson can
  be shown in a one-minute video.
