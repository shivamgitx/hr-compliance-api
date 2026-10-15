# HR Transaction Policy Rules (stand-in)

Stand-in rules written for rehearsal. Replace with the official policy_rules.md when it is published.

Field notes: `amount` is AED per month for Hire, Pay Change and Allowance Change (the change or the starting salary), days for Leave, and 0 for Transfer and Exit. Dates and timestamps are ISO format. Grades run G1 (lowest) to G9 (highest). Timing rules use calendar days.

| Rule | Category | Rule text | Default severity | Owner |
|---|---|---|---|---|
| R01 | Segregation of duties | The requester of a transaction cannot also be its first or second approver. | High | HR Compliance |
| R02 | Segregation of duties | The first and second approver of a transaction must be different people. | High | HR Compliance |
| R03 | Approval authority | The first approver must be at a higher grade than the employee. For a G9 employee the first approver must also be G9. | High | HR Compliance |
| R04 | Approval limits | A Pay Change above AED 2,000 per month (grades G1-G4), AED 4,000 (G5-G6) or AED 8,000 (G7-G9) requires a second approver. | High | Compensation and Payroll |
| R05 | Approval limits | A Pay Change above AED 15,000 per month requires a second approver at grade G9. | High | Compensation and Payroll |
| R06 | Approval limits | An Allowance Change cannot exceed the monthly cap for the grade: AED 1,500 (G1-G4), 3,000 (G5-G6), 6,000 (G7-G8), 10,000 (G9). | Medium | Compensation and Payroll |
| R07 | Required documents | A Hire must carry offer_letter, id_copy, medical_clearance and degree_certificate. | Medium | HR Operations |
| R08 | Required documents | An Exit must carry resignation_letter and clearance_form. | Medium | HR Operations |
| R09 | Required documents | A Pay Change must carry approval_memo. An Allowance Change must carry justification_memo. | Medium | HR Operations |
| R10 | Required documents | A Transfer must carry transfer_form. | Low | HR Operations |
| R11 | Required documents | A Leave must carry leave_form. A Leave of more than 30 days must also carry medical_certificate. | Medium | HR Operations |
| R12 | Approval limits | A Leave of more than 30 days requires a second approver. | Medium | HR Operations |
| R13 | Approval limits | Every transaction for an employee at grade G8 or G9 requires a second approver. | High | HR Compliance |
| R14 | Timing windows | A Pay Change or Allowance Change cannot be backdated: the effective date cannot be more than 30 days before the approval date. | Medium | Compensation and Payroll |
| R15 | Timing windows | A Hire or Transfer must be approved on or before its effective date. | Medium | HR Operations |
| R16 | Timing windows | A transaction must be approved within 10 calendar days of submission. | Low | HR Operations |
| R17 | Duplicates | Two transactions with the same employee, type and effective date are duplicates. The later submission is the exception. | Medium | HR Operations |
| R18 | Employment status | No Pay Change, Allowance Change, Transfer or Leave can take effect after the employee's exit date. | High | Payroll Operations |
