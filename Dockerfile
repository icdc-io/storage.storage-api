# FROM fedora:40
# NOTE: Use our repo to workaround docker.hub limits

ARG CR_SERVER

FROM ${CR_SERVER:-docker.io}/fedora:40

# Metadata as described above
LABEL author1="icdc@ibagroup.eu" \
      author2="skuzko@ibagroup.eu"

########################
# System updates and repository configuration
########################
RUN dnf -y update && \
    dnf -y install wget python3 python3-pip python3-rados python3-rbd && \
    dnf clean all

########################
# Install websocat
########################
RUN wget -qO /usr/local/bin/websocat https://github.com/vi/websocat/releases/latest/download/websocat.x86_64-unknown-linux-musl && \
    chmod a+x /usr/local/bin/websocat

########################
# Python environment setup
########################
WORKDIR /usr/src/app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Python libraries from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

########################
# Security adjustments and permissions
########################
RUN rm -rf .git && \
    chgrp -R 0 /usr/src/app && \
    chmod -R g+rwX /usr/src/app && \
    chmod -R 777 /etc && \
    chmod g=u /etc/passwd && \
    chmod 777 /usr/src/app/entrypoint.sh

# Expose port 8080
EXPOSE 8080

# Run the application
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:flask_app"]
