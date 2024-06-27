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

# Run with flask (local only)
#ENTRYPOINT [ "python3", "/python/ims_service/ims_service.py" ]

# Run with gunicorn
ENV PORT 5000
ENV WORKERS 2
ENV LOGLEVEL info

EXPOSE $PORT

# Create entry script to run service
RUN echo "#!/bin/sh" > /app/entry.sh && \
    echo "gunicorn --chdir /app -w \${WORKERS}  \\" >> /app/entry.sh && \
    echo "   -b 0.0.0.0:\${PORT} --worker-tmp-dir /dev/shm \\" >> /app/entry.sh && \
    echo "   --enable-stdio-inheritance --access-logfile - --error-logfile - \\"  >> /app/entry.sh && \
    echo "   --access-logformat '%(h)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\" %(T)s %(M)s' \\"  >> /app/entry.sh && \
    echo "    --log-level \${LOGLEVEL} 'app:app' " >> /app/entry.sh && \
    chmod a+x /app/entry.sh

ENTRYPOINT ["/app/entry.sh"]