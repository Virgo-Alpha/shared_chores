# Shared Household Chore Manager --- Homework Plan

## 1. Purpose

Build a tool for managing shared household chores and one-off household
tasks. The system should work for different household structures,
including couples, families, and roommates.

The homework should focus on practical household task management without
introducing unnecessary complexity such as multi-household membership,
task dependencies, or workflow engines.

## 2. Household and Users

-   The system supports any type of household: couples, families, or
    roommates.
-   Each user belongs to exactly one household.
-   Household members do not self-register into a household.
-   An Owner/Admin creates accounts for household members.
-   Authentication uses email and password.
-   Social login is out of scope.

### Roles

Use role-based permissions.

Suggested roles:

-   **Owner/Admin** --- manages the household, members, and chores.
-   **Member** --- normal household participant.
-   **Child/Restricted Member** --- limited permissions.

## 3. Tasks and Chores

Use one unified task model rather than separate models for chores and
one-off jobs.

Each task has a `type` trait, initially supporting:

-   `CHORE`
-   `ONE_OFF`

Examples:

-   CHORE: Wash dishes every evening.
-   CHORE: Clean bathroom every Saturday.
-   ONE_OFF: Fix leaking tap.
-   ONE_OFF: Buy a new vacuum cleaner.

### Optional Task Attributes

A task may optionally have:

-   Priority, such as low, medium, or high.
-   Estimated effort/time.
-   Workload weight or points.
-   Description.
-   Category.
-   Due time.

A due date is supported, with an optional due time.

## 4. Categories

Tasks can be organized using categories.

Provide sensible system defaults, for example:

-   Cleaning
-   Cooking
-   Laundry
-   Shopping
-   Maintenance

Households can also create their own custom categories.

Location/room-based organization is not required.

## 5. Assignment

The tool supports a hybrid assignment model.

Tasks may be:

-   Manually assigned.
-   Assigned using rotation.
-   Placed in a pool for members to claim.
-   Automatically assigned using a fair assignment mechanism.

For automatic assignment, fairness should remain simple and
deterministic: use **round-robin rotation** rather than a complex
workload/availability algorithm.

### Number of Assignees

A task can support:

1.  **Single assignee** --- one person is responsible.
2.  **Joint assignment** --- multiple assigned members must complete it.
3.  **Any-of assignment** --- several members are eligible, but one
    completion satisfies the task.

The assignment mode is selected per task.

## 6. Recurrence

Recurring chores support all of the following:

### Simple recurrence

Examples:

-   Daily
-   Weekly
-   Monthly

### Flexible recurrence rules

Examples:

-   Every 3 days.
-   Weekdays only.
-   First Saturday of every month.

### Completion-relative recurrence

The next occurrence can be calculated from the previous completion.

Example:

> Clean the aquarium 14 days after it was last cleaned.

### Missed Recurring Chores

If a recurring chore is missed, the occurrence remains **overdue until
completed**.

It should not automatically be skipped merely because its scheduled date
has passed.

## 7. Completion

Completing a task should always record:

-   Who completed it.
-   When it was completed.

Individual tasks can optionally require additional completion controls.

### Proof

A task may require proof, such as:

-   A photo.
-   A completion note.

### Approval

A task may require another authorized household member to verify/approve
completion.

Proof and approval are configurable per task and are not required for
ordinary chores.

## 8. Checklists

Tasks can optionally contain a simple checklist.

Example:

**Clean kitchen**

-   Wipe counters.
-   Clean sink.
-   Empty bin.
-   Mop floor.

Checklist items are components of the parent task, not independent
tasks.

Therefore checklist items do **not** have their own:

-   Assignees.
-   Due dates.
-   Recurrence schedules.
-   Notifications.

## 9. Task Independence

Tasks remain independent.

The homework explicitly excludes:

-   Task dependencies.
-   Blocking/unblocking tasks.
-   Workflow graphs.
-   Reusable workflow templates.

For example, the system does not need to enforce that "Wash clothes"
must finish before "Fold clothes."

## 10. Workload and Gamification

Basic fairness/workload tracking is part of the normal system.

The tool should make it possible to see how household work is
distributed between members.

Gamification is optional and configurable.

Optional features include:

-   Points.
-   Streaks.
-   Household-defined rewards.

The optional workload weight/points on a task can allow larger chores to
count more than trivial chores.

## 11. Views

The application should provide multiple useful views rather than relying
on a single task list.

### Today View

Shows chores relevant to the current day.

### Household Board

Shows household tasks across members.

### Calendar

Shows tasks according to their scheduled/due dates.

### Personal Dashboard

Shows information relevant to the logged-in user, such as:

-   Assigned chores.
-   Due chores.
-   Overdue chores.
-   Completed chores.
-   Workload.
-   Points/streaks when gamification is enabled.

## 12. Notifications

Notifications are configurable by the user.

Supported notification events include:

-   Upcoming due task.
-   Overdue task.
-   New assignment.
-   Rotation/assignment change.
-   Task completion.
-   Task awaiting approval.
-   Approval/rejection result.

Due-time reminders can use the optional task due time when one exists.

## 13. Explicitly Out of Scope

To keep the homework bounded, the following are not required:

-   Multiple households per user.
-   Household invitation links/codes.
-   Email household invitations.
-   Social authentication.
-   Task dependencies.
-   Workflow engines.
-   Reusable task workflows.
-   Individually assignable subtasks.
-   Separate due dates for checklist items.
-   Complex AI/optimization-based chore assignment.
-   Location/room organization.

## 14. Core Domain Model

A reasonable starting domain model is:

-   **Household**
-   **User**
-   **HouseholdMembership / Role**
-   **Task**
-   **Category**
-   **TaskAssignment**
-   **ChecklistItem**
-   **RecurrenceRule**
-   **TaskOccurrence**
-   **Completion**
-   **CompletionProof**
-   **Approval**
-   **NotificationPreference**

Optional gamification may introduce:

-   **PointsLedger**
-   **Reward**
-   **Streak**

The exact database schema should be designed during implementation; this
list defines the conceptual scope rather than requiring one database
table per item.

## 15. Scope Summary

The homework is a **single-household chore and household-task management
application**.

Its core flow is:

**Admin creates household members → household creates chores/tasks →
tasks are scheduled or recur → tasks are manually assigned, claimed, or
rotated → members complete them → optional proof/approval occurs →
workload and completion history are recorded → users receive
configurable notifications.**

The emphasis should be on getting this lifecycle correct before adding
optional gamification or other enhancements.
