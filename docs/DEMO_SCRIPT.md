# ChurnLens: 2-minute demo

Before you start: open the app once so the backend is awake (the free tier sleeps), and
have the sample flow finished in one tab so you can jump straight to the dashboard.

| Time | Show | Say |
| --- | --- | --- |
| 0:00 | Home page | "ChurnLens turns a customer file into a churn analysis with a team of agents, and every number is checked." |
| 0:10 | Press **Try sample data** | "7,000 telecom customers. An agent proposes the schema; I stay in control." |
| 0:20 | Schema confirmation | "It found the churn column, the ID and the offer columns. I confirm." (Switch to the finished tab.) |
| 0:30 | Executive Overview | "Churn is 25.66%. These insights were written by the AI, but the badge says every number was verified against the computed results." |
| 0:45 | Churn Drivers | "Contract type and tenure drive churn, by permutation importance, SHAP and odds ratios. Associations, not causes." |
| 0:55 | Model Performance | "Calibrated model: of the 10% of customers we flag, about 70% really churn." |
| 1:05 | Risk Predictions → a High-risk customer | "Each customer has reasons and a next best offer, with the formula behind it." |
| 1:15 | Business Impact → months remaining 12 → 24 | "Money figures are assumptions, labelled with their source. I change one and Python recomputes; the AI explanation is flagged as based on the old numbers." |
| 1:30 | Experiments → **Load demo experiment** | "Before rolling an offer out, test it. This simulated test has a known effect: the confidence interval finds it, and the verdict is only a suggestion; a person decides." |
| 1:45 | Ask the Data → "Churn rate by Contract for tenure under 12 months" | "The chat agent can only use five whitelisted tools; it shows which one it used." |
| 1:55 | Download PDF report | "And the whole analysis exports to Excel and PDF." |

Backup questions if asked:
- *How do you stop the LLM inventing numbers?* Every figure carries a `source_key`; the
  validator resolves it, compares the value and rejects undeclared numbers. Failing items
  are retried twice, then dropped (see Agent Health).
- *Is the model trustworthy?* Metrics are on a held-out test split; probabilities are
  calibrated on the training split only; a leakage guard rejects ROC-AUC above 0.99.
- *What does it cost?* The Agent Health tab shows tokens and an estimated cost per run;
  the free Gemini tier costs nothing.
