# Cloud Notes: standing rules for every task

## Mission
Build Cloud Notes, a polished student notes web app that runs on AWS. Notes are Markdown files (S3 in the cloud, a local folder in development). Quality bar: it must look and feel like a real product, comparable to Apple Notes, Notion or Memos. It must not look like a tutorial project.

## Always do first
1. Read docs/SPEC.md completely. It is the single source of truth for features, design tokens, data model and API. Do not contradict it.
2. Read PROGRESS.md to see what is already done.
3. Do only the current stage. Do not add features that are not in the spec.

## Fixed technology (do not substitute anything)
- Backend: Python 3.12, Flask 3, SQLAlchemy 2, PyMySQL, PyJWT, bcrypt, boto3, python-frontmatter, gunicorn, pytest.
- Frontend: React 18, Vite, TypeScript (strict), Tailwind CSS, shadcn/ui, lucide-react, TanStack Query, Zustand, React Router, Sonner, @milkdown/crepe, @fontsource-variable/inter.
- Database: SQLite in local dev, MySQL 8 in Docker Compose and on AWS RDS, selected by DATABASE_URL.
- Storage: STORAGE_BACKEND=local or s3.
- Deploy: one Docker image, AWS CloudFormation, ALB, Auto Scaling, CloudWatch.
- Library APIs change. Before using a library, read its installed version's types or official docs. Never guess an API.

## Engineering rules
- Never hard-code secrets, keys, passwords or account ids. Use environment variables. Keep .env out of Git and provide .env.example.
- Every backend route validates input, scopes queries to the current user, and returns the error format in the spec.
- Write pytest tests for backend logic. Run them and show the result before saying a stage is done.
- Keep files small and named clearly. Add short comments only where logic is not obvious.
- Handle loading, empty and error states in every screen.
- Follow the design tokens in the spec exactly. Do not invent colours, fonts or spacing.
- If something in the spec is ambiguous, choose the simplest option, and write the choice in PROGRESS.md under Decisions.
- Never run destructive commands (rm -rf, aws delete/terminate commands, git push --force) without asking me first, and explain the exact effect.
- Never create AWS resources that cost money outside the CloudFormation stack defined in infra/. Never create a NAT Gateway.

## Finishing every stage
1. Run the app or the tests and verify the stage's "Done when" list yourself. For UI work, open the app in the browser, test it, and take screenshots into docs/screenshots/.
2. Update PROGRESS.md: what was built, how to run it, what is next, any decisions or known issues.
3. Make a git commit with a clear message.
4. Finish with a short summary and the exact commands I should run to see it working.
F4. First commit. In the Antigravity terminal run: git init, git add ., git commit -m "Add rules and spec", then connect to your GitHub repo as shown on its empty-repository page and git push -u origin main.