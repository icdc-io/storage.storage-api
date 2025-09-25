# Storage API

![Pipeline status](https://code.icz.icdc.io/icdc/storage/storage-api/badges/dev/pipeline.svg)
![Coverage](https://code.icz.icdc.io/icdc/storage/storage-api/badges/dev/coverage.svg)

## Storage Container

This document provides instructions on how to build and run the `storage` container using Podman.

### Prerequisites

- Ensure that you have [Podman](https://podman.io/getting-started/installation) installed on your machine.

### Building the Container

To build the `storage` container, navigate to the directory containing the Dockerfile and run the following command:

```bash
    docker/podman build -t storage .
    # or if there is the container registry server
    docker/podman build --build-arg CR_SERVER=$CR_SERVER -t storage .
````

### Running the Container

To run the storage container with host networking enabled:

```bash
    docker/podman run --network host --name storage -it --rm localhost/storage:latest bash
```

```text
`--network host`: This option ensures that the container shares the network namespace with the host.

`--name storage`: Specifies a name for the running container.

`-it`: Runs the container in interactive mode with a terminal attached.

`--rm`: Removes the container once it stops running.

`localhost/storage:latest`: This is the name of the image to run, which we previously built and tagged as storage.
```

After executing the above command, you will be inside the container's shell (bash).

### Stopping the Container

If you need to stop the container:

```bash
docker/podman stop storage
```

### Setup Instructions OC Console

Download the oc Client:

Use the following command to download the oc client:

```bash
    wget https://mirror.openshift.com/pub/openshift-v4/clients/oc/latest/linux/oc.tar.gz
```

Extract the Archive:

```bash
    tar -xzf oc.tar.gz
```

Move `oc` to Your Path (Optional but Recommended):

For ease of use, you might want to move the `oc` binary to a directory in your system's PATH. For instance, `/usr/local/bin` is a common choice:

```bash
    sudo mv oc /usr/local/bin/
```

Verify Installation:

Check the version of the `oc` client to ensure it's installed correctly:

```bash
    oc version
```

Cleanup:

You can remove the downloaded archive after the installation:

```bash
    rm oc.tar.gz
```

Usage

Now that you've set up the `oc` client, you can use it to interact with your OpenShift or OKD cluster. For further details on using `oc`, refer to the official OpenShift documentation.

### Deployment on Openshift

You will need the `ceph.conf` file:

```text
# example ceph.conf
# minimal ceph.conf for 07711b9a-78b9-11ee-9f4b-1cdc1500004e
[global]
 fsid = 07711b9a-78b9-11ee-9f4b-1cdc1500004e
 mon_host = [v2:10.254.20.17:3300/0,v1:10.254.20.17:6789/0] [v2:10.254.20.32:3300/0,v1:10.254.20.32:6789/0] [v2:10.254.20.39:3300/0,v1:10.254.20.39:6789/0]
# must be last line
```

You will also need the `ceph.client.storage.keyring` file.

### Integration Tests

Before running integration tests, you need to have the `storage` image built and create environment variables for the database connection: `DATABASE_USERNAME`, `DATABASE_PASSWORD`, and `DATABASE_NAME`.

To run the integration tests, execute the following command:

```bash
    export DATABASE_USERNAME="storage_username"
    export DATABASE_PASSWORD="storage_password"
    export DATABASE_NAME="storage_database"

    # for mounting into the test container
    touch report.xml
    mkdir htmlcov

    ./run_tests.sh storage

    # cleanup test results if needed
    rm -rf htmlcov report.xml
```

---

## Using `pre-commit` Hooks

`pre-commit` hooks help automate checks (like linting and formatting) before committing your changes. Here's how to set them up for this project:

### Installation

1. First, you need to install the `pre-commit` package if you haven't done so already:

   ```bash
   pip install pre-commit
   ```

2. Then, install the Git hooks by running the following command in your project directory:

   ```bash
   pre-commit install
   ```

   This will set up the hooks to run automatically before each commit.

3. Optionally, if you want the hooks to run before a `git push`, you can also install the `pre-push` hook:

   ```bash
   pre-commit install --hook-type pre-push
   ```

### Running Hooks Manually

You can run all hooks manually at any time with:

```bash
pre-commit run -a
```

This will run all hooks on all files in the repository, not just the staged ones.

### Hooks in Action

The pre-commit hooks in this project will automatically run various checks, such as:

- **Ruff**: A fast Python linter.
- **Black**: A Python code formatter.(future)
- **Pylint**: Another Python linter to catch style issues.(future)

These hooks will automatically attempt to fix any issues where possible before allowing you to commit your changes.

### Customizing Hooks

If you want to customize or add more hooks, you can modify the `.pre-commit-config.yaml` file located in the root of the project.
