#Storage API

![Pipeline status](https://code.icz.icdc.io/icdc/storage/storage-api/badges/dev/pipeline.svg)
![Coverage](https://code.icz.icdc.io/icdc/storage/storage-api/badges/dev/coverage.svg)

# Storage-v2 Container

This document provides instructions on how to build and run the `storage-v2` container using Podman.

## Prerequisites

- Ensure that you have [Podman](https://podman.io/getting-started/installation) installed on your machine.

## Building the Container

To build the `storage-v2` container, navigate to the directory containing the Dockerfile and run the following command:

```bash
    docker/podman build . -t storage-v2
```

## Running the Container

To run the storage-v2 container with host networking enabled:

```bash
    docker/podman run --network host --name storage-v2 -it --rm localhost/storage-v2:latest bash
```

    `--network host`: This option ensures that the container shares the network namespace with the host.

    `--name storage-v2`: Specifies a name for the running container.

    `-it`: Runs the container in interactive mode with a terminal attached.

    `--rm`: Removes the container once it stops running.

    `localhost/storage-v2:latest`: This is the name of the image to run, which we previously built and tagged as storage-v2.

After executing the above command, you will be inside the container's shell (bash).

## Stopping the Container

If you need to stop the container:

```bash
docker/podman stop storage-v2
```

## Setup Instructions OC console

Download the oc Client:

Use the following command to download the oc client:

```bash
    wget https://mirror.openshift.com/pub/openshift-v4/clients/oc/latest/linux/oc.tar.gz
```

Extract the Archive:

```bash
    tar -xzf oc.tar.gz
```

Move oc to Your Path (Optional but Recommended):

For ease of use, you might want to move the oc binary to a directory in your system's PATH. For instance, /usr/local/bin is a common choice:

```bash
    sudo mv oc /usr/local/bin/
```

Verify Installation:

Check the version of the oc client to ensure it's installed correctly:

```bash
    oc version
```

Cleanup:
You can remove the downloaded archive after the installation:

```bash
    rm oc.tar.gz
```

Usage

Now that you've set up the oc client, you can use it to interact with your OpenShift or OKD cluster. For further details on using oc, refer to the official OpenShift documentation.

## Deplot on Openshift

Need file ceph.conf

```text
#example ceph.conf
# minimal ceph.conf for 07711b9a-78b9-11ee-9f4b-1cdc1500004e
[global]
 fsid = 07711b9a-78b9-11ee-9f4b-1cdc1500004e
 mon_host = [v2:10.254.20.17:3300/0,v1:10.254.20.17:6789/0] [v2:10.254.20.32:3300/0,v1:10.254.20.32:6789/0] [v2:10.254.20.39:3300/0,v1:10.254.20.39:6789/0]
# must be last line
```

Need file ceph.client.storage.keyring
