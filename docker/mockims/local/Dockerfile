# IMS Gateway Request Service using python sci base image
# sci is required because the use of shapely
FROM idss.engine.commons.python-base:local

ARG maintainer
LABEL maintainer ${maintainer}

# Install additional dependencies
#RUN conda config --add channels conda-forge && \
#    conda install -y <package>=<1.0.0>

WORKDIR /python/ims_service

# Copy source files
COPY ./python/idsse_testing/ims_service/src/ims_service.py /python/ims_service/

# (TEMPORARY) Copy canned criteria files. To be removed when integration with IMS API exists
COPY ./python/idss_testing/ims_service/profiles/*.json /python/profiles/

# If you need to have a local mount, otherwise service will use version controlled jsons
#VOLUME /python/profiles

ENTRYPOINT [ "python3", "/python/ims_service/ims_service.py" ]