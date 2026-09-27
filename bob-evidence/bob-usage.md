# IBM Bob Usage Statement

IBM Bob 2.0 was used throughout the development of GitHub-DNA as an
AI-assisted development environment for planning, implementation,
testing, debugging, and refinement.

The development process began with Bob's document understanding
capabilities. Bob was given the project's architecture specification and
asked to understand the problem, proposed architecture, components,
data flow, technologies, MVP requirements, and potential issues before
implementation.

Bob's Plan mode was then used to break the project into manageable
implementation milestones. The development was divided into repository
file discovery, Python dependency analysis, Git history analysis,
repository graph and metrics, and frontend visualization.

Bob's Agent mode was used to implement these milestones individually.
After each milestone, Bob was instructed to run the relevant tests,
identify failures, and fix them before moving forward. This resulted in
a progressively tested implementation rather than generating the entire
application at once.

Bob's subagent capabilities were also used during the Git history
milestone. A read-only Explore subagent inspected the existing project
structure and implementation plans and provided recommendations for a
simple Git history analyzer before the main Agent implemented it.

Bob was also used for debugging and refinement. During development, it
helped fix repository scanning so generated and dependency directories
were ignored, and improved dependency analysis so test files and
multi-level Python imports were correctly represented in the repository
graph.

For the frontend, Bob assisted with implementing the React-based
visualization, repository metrics interface, dark theme, hierarchical
graph layout, and interactive file details panel.

Testing was performed throughout development using pytest, with Bob
running the test suite after implementation milestones and fixing
failures where necessary.

The developer directed the development process, reviewed the generated
changes, tested the application, and decided which changes to keep.
Bob was therefore used as an engineering assistant across the
development lifecycle rather than as a replacement for developer
decision-making.
