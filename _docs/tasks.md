# Shared Chores Backlog

## 1. Set up an empty project with a passing test
Goal: Establish a minimal Django project and app that runs successfully.
Description: Create the project structure, install the required dependencies, and configure the application. Add one basic test proving the empty project loads and passes.

## 2. Add email-based user authentication
Goal: Let users sign in with an email address and password.
Description: Create the custom user model and configure Django authentication to use email as the login identifier. Add tests for creating users, authenticating valid credentials, and rejecting invalid credentials.

## 3. Create the household model
Goal: Represent the single household managed by the application.
Description: Add a household model with the identifying fields needed by the product. Include migrations and model tests for creating and displaying a household.

## 4. Add household membership and roles
Goal: Associate each user with one household and one supported role.
Description: Add household membership records with Owner/Admin, Member, and Child/Restricted Member roles. Enforce the one-household-per-user rule and test the role values and relationships.

## 5. Add household member administration
Goal: Allow an Owner/Admin to create and manage household member accounts.
Description: Build the forms and views needed for an authorized owner to add, edit, and deactivate members. Add permission tests proving ordinary members cannot manage accounts.

## 6. Create categories and default category data
Goal: Organize tasks by reusable household categories.
Description: Add a category model linked to a household and create the default Cleaning, Cooking, Laundry, Shopping, and Maintenance categories. Support household-created categories and test household isolation.

## 7. Create the core task model
Goal: Store chores and one-off household tasks in one model.
Description: Add task fields for title, description, type, priority, estimated effort, workload points, category, due date, and optional due time. Support the CHORE and ONE_OFF types with validation and model tests.

## 8. Add task creation and editing
Goal: Let authorized household users manage task details.
Description: Build task forms and views for creating, editing, viewing, and deleting tasks. Enforce household ownership and test that unauthorized users cannot modify another household’s tasks.

## 9. Add task assignment modes
Goal: Support single, joint, and any-of task assignments.
Description: Add assignment records and the task setting that determines how assignees participate. Validate the allowed combinations and test assignment behavior for each mode.

## 10. Implement round-robin assignment
Goal: Assign recurring work fairly with a deterministic rotation.
Description: Add the state needed to remember the next household member in a rotation and implement round-robin selection. Test ordering, wraparound, and behavior when a member is inactive.

## 11. Add claimable task pools
Goal: Let eligible members claim tasks that have no fixed assignee.
Description: Add a pool assignment option and an action for an eligible member to claim an available task. Prevent duplicate claims and test that a claim satisfies the configured assignment rules.

## 12. Add recurrence rules
Goal: Define when a chore repeats.
Description: Add recurrence data for daily, weekly, monthly, interval-based, weekday-based, and monthly-position rules. Validate rule inputs and test calculating the next scheduled date for representative cases.

## 13. Track task occurrences and overdue chores
Goal: Keep each scheduled occurrence visible until it is completed.
Description: Add task occurrence records generated from recurrence rules and expose their scheduled and overdue states. Test that missed recurring chores remain overdue instead of being silently skipped.

## 14. Add task checklists
Goal: Support simple checklists inside a task.
Description: Add ordered checklist items belonging to a parent task without independent assignees, dates, or recurrence. Provide create, edit, reorder, and completion behavior with focused tests.

## 15. Record task completion
Goal: Record who completed a task and when.
Description: Add completion records linked to the relevant task occurrence and user. Implement completion actions and test single, joint, and any-of assignment completion rules.

## 16. Add completion proof and approval
Goal: Support optional evidence and verification for completed tasks.
Description: Allow a task to require a completion note, photo, and/or approval by an authorized household member. Add workflows and tests for submission, approval, rejection, and ordinary tasks that require neither.

## 17. Build the personal dashboard
Goal: Show each user the work relevant to them.
Description: Create a dashboard containing assigned, due, overdue, and completed tasks for the signed-in user. Add workload totals and permission tests confirming users see only their household data.

## 18. Build the household task board
Goal: Show household work across members in one view.
Description: Create a board grouped by assignee and task status, including unassigned and claimable tasks. Add filters for status, type, category, and priority with view tests for the main combinations.

## 19. Build the calendar view
Goal: Display tasks and occurrences by scheduled date.
Description: Add a calendar view that includes due dates, optional due times, recurring occurrences, and overdue work. Test date boundaries and that users cannot see events from another household.

## 20. Add notification preferences
Goal: Let users choose which task events notify them.
Description: Add per-user preferences for upcoming due tasks, overdue tasks, assignments, rotation changes, completions, approval requests, and approval results. Provide defaults and test saving and applying preferences.

## 21. Generate task notifications
Goal: Deliver configured notifications for supported task events.
Description: Implement notification creation for assignments, due reminders, overdue tasks, completions, and approval changes. Keep notification generation deterministic and test that disabled preferences suppress the corresponding events.

## 22. Add workload reporting
Goal: Make household work distribution visible.
Description: Calculate completed workload by member using task effort or points and a defined reporting period. Add a household report and tests covering unassigned work, completed work, and different task weights.

## 23. Add optional points and streaks
Goal: Provide configurable gamification without affecting core task completion.
Description: Add settings that enable points and streak tracking for a household. Record points and calculate streaks only when enabled, with tests proving the feature can remain disabled.

## 24. Add authorization coverage and regression tests
Goal: Protect household boundaries and core permissions as features grow.
Description: Review every task, member, category, completion, and notification endpoint for authentication and household authorization. Add regression tests for cross-household access, restricted members, and anonymous users.