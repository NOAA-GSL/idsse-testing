# NWSC Proxy Service using python commons base image
FROM ghcr.io/noaa-gsl/idss/commons/python/python-base:main

ARG maintainer
LABEL maintainer ${maintainer}

# Install additional dependencies
#RUN conda config --add channels conda-forge && \
#    conda install -y flask=2.3.2

WORKDIR /python/nwsc_proxy

# Copy source files
COPY ./python/nwsc_proxy/*.py /python/nwsc_proxy/
COPY ./python/nwsc_proxy/src/*.py /python/nwsc_proxy/src/

# Don't copy canned profiles for UAT, use criteria builder to generate needed profiles
#COPY ./python/nwsc_proxy/src/profiles/*.json /python/profiles/

# The volume mapping here is kind of strange for k8s deployment, because if we map an empty volume to /criteria
# then the temp copy of json above will get blown away by the volume mapping...just omit it for k8s deployment
# for now.
#VOLUME /python/profiles

ENTRYPOINT [ "python3", "/python/nwsc_proxy/ncp_web_service.py", "--base_dir", "/python/profiles"]
