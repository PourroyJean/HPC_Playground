#!/usr/bin/env bash
set -e

BRANCH="main"

# Check if the working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "Local changes detected. Please commit or stash them before running this script."
    exit 1
fi

echo "Fetching updates from both repositories..."
git fetch origin $BRANCH
git fetch public $BRANCH

# Get the HEAD commits from both remotes
OHEAD=$(git rev-parse origin/$BRANCH)
PHEAD=$(git rev-parse public/$BRANCH)

echo "Comparing commits..."
if [ "$OHEAD" = "$PHEAD" ]; then
    echo "Both repositories are already synchronized."
    exit 0
fi

# Check if one repo is an ancestor of the other
if git merge-base --is-ancestor $OHEAD $PHEAD; then
    # origin is an ancestor of public → public is ahead
    echo "The external (public) repository is ahead. Synchronizing external -> internal..."
    git checkout $BRANCH
    git pull public $BRANCH
    git push origin $BRANCH
    echo "External -> Internal synchronization complete."
elif git merge-base --is-ancestor $PHEAD $OHEAD; then
    # public is an ancestor of origin → origin is ahead
    echo "The internal (origin) repository is ahead. Synchronizing internal -> external..."
    git checkout $BRANCH
    git pull origin $BRANCH
    git push public $BRANCH
    echo "Internal -> External synchronization complete."
else
    # Neither is ancestor of the other → divergence
    echo "The repositories have diverged. Manual conflict resolution is required."
    echo "To resolve this:"
    echo "1. On this machine, run 'git pull origin main' and 'git pull public main' (perhaps in a separate branch) to bring all changes locally."
    echo "2. Resolve any merge conflicts that arise."
    echo "3. Commit the resolved changes."
    echo "4. Push the updated, conflict-free branch to both remotes: 'git push origin main' and 'git push public main'."
    echo "After this, you can rerun this script to continue automatic syncing."
    exit 1
fi
