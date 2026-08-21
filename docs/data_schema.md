# ASSISTments 2009–2010 Skill Builder — Data Description

Source: https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/skill-builder-data-2009-2010

> If you use this dataset in a publication, cite the URL above.

## Column reference

| Field | Annotation |
|---|---|
| `order_id` | Non-chronological id, refers to original problem log |
| `assignment_id` | Each assignment is specific to a single teacher/class |
| `user_id` | Id of the student |
| `problem_id` | Id of the problem |
| `original` | Main problem or scaffolding problem |
| `correct` | Correct on the first attempt, incorrect on the first attempt, or asked for help |
| `attempt_count` | Number of attempts by the student |
| `ms_first_response` | Time in milliseconds for the student's first response |
| `tutor_mode` | `tutor` or `test` |
| `answer_type` | `choose_1`, `algebra`, `fill_in`, or `open_response` |
| `sequence_id` | Id of the problem set |
| `student_class_id` | Class id |
| `position` | Assignment position on the class assignments page |
| `type` (problem set type) | `Linear`, `Random`, or `Mastery` |
| `base_sequence_id` | If the sequence has been copied, points to the original copy |
| `skill_id` | Id of the skill associated with the problem. In this skill-builder dataset, records are duplicated so each row has exactly one skill |
| `skill_name` | Name of the skill |
| `teacher_id` | Id of the teacher |
| `school_id` | Id of the school |
| `hint_count` | Number of hints the student used |
| `hint_total` | Number of possible hints on the problem |
| `overlap_time` | Time in milliseconds |
| `template_id` | Template id of the ASSISTment; items sharing a template id are similar questions |
| `answer_id` | Answer id for multiple-choice questions |
| `answer_text` | Answer text for fill-in questions |
| `first_action` | Type of first action: attempt or ask for a hint |
| `bottom_hint` | Whether the student asked for all hints |
| `opportunity` | Number of opportunities the student has had to practice this skill |
| `opportunity_original` | Same as `opportunity`, counting only original (non-scaffolding) problems |

### Notes on discrepancies vs. the raw CSV

- The CSV also contains an `assistment_id` column that is **not documented** by the source site. It sits alongside `problem_id` and appears to be a separate item-instance identifier — treat its exact semantics as unconfirmed until checked in EDA.
- `hint_count`'s source annotation literally reads "number of student attempts," which duplicates the description of `attempt_count`. This is almost certainly a copy-paste error on the source site — `hint_count` is used here per the ASSISTments convention (number of hints requested), paired with `hint_total` (hints available).

## Key dataset features

- **Mastery-learning design**: records student problem-solving steps where tasks tie directly to designated knowledge components (skills).
- **Row structure**: each row logs one student interaction with a problem, tracking correctness, attempts, and hint usage.
- **Duplicate rows are intentional**: a problem tagged with multiple skills is split into one duplicate row per skill (varying `skill_id`, `skill_name`, `opportunity`, `opportunity_original`). This is documented behavior, not a data error — distinct from accidental exact-duplicate rows, which should still be checked for separately.
- Data consists of student interaction logs from an online mathematics tutoring platform (ASSISTments, created by Neil Heffernan and Ken Koedinger, 2003).
