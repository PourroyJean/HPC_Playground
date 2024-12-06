### Synchronizing the HPC_Playground Repositories

This repository hosts a script (`auto_sync.sh`) that automatically synchronizes changes between the internal HPE GitHub and its public GitHub counterpart.

### Prerequisites
- Ensure that your SSH keys are properly configured for both the internal (`git@github.hpe.com:jean-pourroy/HPC_Playground.git`) and the external (`git@github.com:PourroyJean/HPC_Playground.git`) repositories.

### Usage
1. In Grenoble, navigate to the repository directory:
    ```bash
    cd /nfs/pourroy/code/HPC_Playground
    ```
2. Make sure your working directory is clean (commit or stash any local changes).

3. Run the synchronization script:
    ```bash
    ./auto_sync.sh
    ```
The script will:
- Check if your working directory is clean.
- Determine which repository is ahead.
- Automatically synchronize changes in the appropriate direction.
- If there is a divergence, it will stop and prompt you to resolve conflicts manually.
