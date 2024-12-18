# NWS Connect Proxy Service

 ## Overview
-The `nwsc-dummy-service` is a web service that simulates storing a set of Support Profiles and serving them up in a simple REST interface.

## Configurations
The NWS Connect proxy service should be started as a standalone service and offers two end-points in support of the NWSConnect Gateway request/response services. Those services should be provided with the network address of this services endpoints via their command line arguments for testing purposes.


## Build, Release, and Run
The subsections below outline how to build the images within this project. All microservices built with Docker are done within the
[idss-engine/build](https://github.com/NOAA-GSL/idss-engine/build/) directory.

**Recommended Tags**
- development: `:dev`
- stable release: `:release` ie. `:alder`
- targeted environment: `:aws`

---
### IMS Service
From the IDSS Engine project root directory `idss-engine/build/<env>/<arch>/`:

`$ docker-compose build proxy_service`

**Local Development Image Name** `idss.engine.service.proxy.service:<tag>`

**Packaged/Deployed Image Name** `idsse/service/proxy/service:<tag>`

---

### Run

See the [Build, Release, Run](https://github.com/NOAA-GSL/idss-engine/blob/main/README.md#running-idss-engine) section within the umbrella project documentation: [idss-engine](https://github.com/NOAA-GSL/idss-engine)

#### Docker

To run this service can run in isolation, it does not requires a rabbitmq server

```
docker run --rm --name proxy-service idss.engine.service.proxy.service:local
```

Optional parameters include:
```
    None
```
#### Python (local)

The most common way to get python dependencies installed is to use either [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html#installing-conda-on-a-system-that-has-other-python-installations-or-packages) or [pip](https://packaging.python.org/en/latest/tutorials/installing-packages/) package managers.

1. Create and activate a virtualenv if you haven't already:
    ```
    python3 -m venv .venv && source .venv/bin/activate
    ```
2. Install 3rd party dependencies
   1. Using pip:
        ```
        pip install flask
        ```
    1. Or using conda (much slower):
        ```
        conda install -c conda-forge python==3.11 pika flask
        ```
3. Import idsse-common library, which is not currently published to any public repository like pip and must be cloned from GitHub manually:
    ```
    pip install --editable /local/path/to/idss-engine-commons
    ```
    - This library uses [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) or [s5cmd](https://github.com/peak/s5cmd/blob/master/README.md#installation) filesystem tools to interact with AWS, so your machine must have one of these installed as well. Example installs using homebrew:
        ```
        brew install awscli
        brew install peak/tap/s5cmd
        ```

Lastly, `cd` to the `./python/nwsc_dummy_service` directory, and start the NWS Connect Dummy service:
```sh
python3 ncd_web_service.py --base_dir /path/to/some/dir
```
