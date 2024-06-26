# IMS Gateway Request Service using python commons base image
FROM ghcr.io/noaa-gsl/idss/commons/python/python-base:main

ARG maintainer
LABEL maintainer ${maintainer}

# Install additional dependencies
#RUN conda config --add channels conda-forge && \
#    conda install -y flask=2.3.2

WORKDIR /python/ims_service

# Copy source files
COPY ./python/idsse_testing/ims_service/src/ims_service.py /python/ims_service/

# (TEMPORARY) Copy canned criteria files. To be removed when integration with IMS API exists
COPY ./python/idsse_testing/ims_service/profiles/*.json /python/profiles/

# The volume mapping here is kind of strange for k8s deployment, because if we map an empty volume to /criteria
# then the temp copy of json above will get blown away by the volume mapping...just omit it for k8s deployment
# for now.
#VOLUME /python/profiles

ENTRYPOINT [ "python3", "/python/ims_service/ims_service.py" ]
