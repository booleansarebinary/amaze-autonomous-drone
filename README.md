# Astrophage documents

## What belongs in the branch

- `docs/astrophage/mission.md`: mission requirements and acceptance evidence.
- `docs/astrophage/design-plan.md`: architecture, phased work, TDD/mutation validation and reporting requirements.
- `Dockerfile`, `compose.yml`, and `.dockerignore`: development scaffold and build-context exclusions.

`local-prompts/codex-prompts.md` is personal working material. Keep it outside the repository, or exclude it locally before copying it in. The prompts reference the two branch documents and retain all master, phase and iteration prompts.

## Recommended: keep prompts outside the repository

Copy `docs/astrophage`, `Dockerfile`, `compose.yml`, and `.dockerignore` into your repository. Keep `local-prompts` elsewhere on your computer, and paste prompts into Codex as needed. If the repository already has Docker configuration, merge these settings into it after inspection rather than overwriting it. This avoids creating any prompt files in your working tree.

## Alternative: local-only prompts in the working tree

From the repository/worktree root in Git Bash, append a local ignore rule before copying `local-prompts` into the root. This does not change the repository's shared `.gitignore`:

```bash
git rev-parse --show-toplevel
git status --short
printf '\n/local-prompts/\n' >> "$(git rev-parse --git-path info/exclude)"
git check-ignore -v --no-index local-prompts/codex-prompts.md
git ls-files -- local-prompts/
```

`git check-ignore` should show the rule; `git ls-files` should print nothing. A local ignore rule does not untrack files already committed or staged. If this file is already tracked and you intend to remove it from the branch while retaining the local copy, inspect status first and use:

```bash
git rm --cached -- local-prompts/codex-prompts.md
```

That stages its removal; review and commit the removal along with the docs. If prompts were already pushed, this does not erase earlier history. Do not rewrite shared history as part of this setup.

## Stage only the intended project files

After copying the documents, from your intended branch/worktree:

```bash
git branch --show-current
git add -- docs/astrophage/mission.md docs/astrophage/design-plan.md Dockerfile compose.yml .dockerignore
git diff --cached --name-only
git diff --cached --check
git diff --cached
```

Review the entire staged list, including pre-existing staged changes. Commit only when it contains the intended changes and no prompt content. Avoid `git add .` and do not force-add the excluded folder.

The earlier combined file `Astrophage_Design_and_Codex_Prompts.md` also contains prompts. Do not copy or stage it as a project document. If it is already tracked in this branch, inspect its actual path and remove that combined file from the branch while preserving a local copy if desired. Merely adding the new split documents does not remove old tracked content.

This package does not modify, commit or push your repository. To use Codex, give it the master prompt followed by Phase 0, then the phase prompts in order.

## Docker development scaffold

The container provides Python 3.12, a native C/C++ compiler and CMake. It is a tooling shell, not a running mission application. It does not install board-specific tools, Python test frameworks, Crazyflie drivers or project dependencies before repository/hardware inspection. Add those through pinned project dependency files when identified. No sensors or radio devices are exposed and no flight commands run.

From the directory containing `compose.yml`, with Docker Engine or Docker Desktop and Compose v2 available:

```bash
mkdir -p logs
docker compose config
docker compose build
docker compose up -d dev
docker compose exec dev bash
```

Inside the container, `python --version`, `g++ --version`, and `cmake --version` check the installed tools. The actual compile/test commands are determined from the repository during Phase 0. Exit the shell, then stop the container with:

```bash
docker compose down
```

Source files are copied into the image at build time. After host edits, run `docker compose up -d --build dev`. Edit on the host: changes elsewhere inside the container are disposable. Only `/workspace/logs` is persisted to `./logs` on the host. Configure runtime exporters to write there. Ignore `/logs/` in Git as well; Docker ignore rules do not affect Git. Linux users should check ownership of files produced by the default root tooling container.

`.dockerignore` excludes `local-prompts/`, the former combined prompt pack, Git internals, common credential files and generated outputs from the build context. It does not change Git tracking and cannot protect files exposed by a later broad bind mount. This Compose file intentionally mounts only logs. No extra Docker build context or root source bind mount is configured.

Hardware access is a later, explicit configuration step. Linux device paths/permissions and Windows/WSL/Docker Desktop USB access differ; a guessed `/dev/ttyUSB0` or privileged container is not part of this scaffold. Initial sensor upload/serial checks may be simpler on the host. Actual devices, board toolchain, serial/radio libraries and dependencies must be confirmed before extending Compose.

Validation performed for this package: YAML structure, Dockerfile/Compose path agreement, archive integrity and exclusion patterns. Docker is unavailable in the document-creation environment, so image builds, `docker compose config`, tool execution inside the image and hardware access have NOT been run. Execute the commands above locally before treating the scaffold as verified.
