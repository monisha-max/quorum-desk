# Quorum

Every suspicious payment at Harbourline gets a hearing before a person freezes it.

Six Gemini agents, built with the Agent Development Kit, sit as a quorum. The clerk opens the file. Ledger, Archivist, and Statute examine it in parallel. Counsel argues the legitimate explanation. The magistrate writes a disposition, a customer note in plain language, and a suspicious-matter draft only when one is earned. An officer files that disposition or overrides it. The customer thread shows the note, and nothing else from the case.

## What a judge should click

1. Open **HL-4374 Priya Nair**. It is live. Convene the quorum. File the hold. Switch to **Customer thread** and read the note that tells her to hang up.
2. Open **HL-4402 Pemba Sherpa**. The rule says structuring. The hearing should release a Dashain transfer to his sister.
3. Open **HL-4366 Lumen Studio**. One payroll credit uses the same account as Priya's scam. The rest of the salaries should still go out.

## Stack

- **Gemini** reasons in every seat, through the Agent Development Kit on Gemini Enterprise.
- **Cloud Run** serves the desk.
- **Firestore** stores each hearing, the disposition, and the officer's decision. The browser never talks to Firestore. Rules deny client access.
- **Firebase Hosting** can front the same Cloud Run service (`firebase.json`). The judging link is the Cloud Run URL.

The ledger features match `sql/features.sql`, which is the BigQuery form of the same mart.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_ENTERPRISE=true
uvicorn quorum.main:app --port 8080
```

A `GOOGLE_API_KEY` from AI Studio also works. If Gemini cannot be reached, the desk files an authored standby brief and says so on the docket. That path is a safety net, not the hearing you want judged.

## Deploy

```bash
bash scripts/deploy.sh
```

The service is `quorum` in `us-central1`, on the `your-project-id` project signed in as you@example.com. Gemini is called in `us-central1`.

## Submission line

Quorum is a financial-crime hearing room. Gemini, through the Agent Development Kit on Cloud Run, hears each alert before an officer does. Firestore keeps the hearing and the officer's decision. Firebase Hosting can front the service, and the customer only ever sees the plain-language note.
