FROM public.ecr.aws/lambda/python:3.12
 
# Switch to root to install system packages
USER root
 
# AL2023 uses dnf instead of yum
RUN dnf install -y \
    postgresql-devel \
    unixODBC-devel \
&& dnf clean all \
&& rm -rf /var/cache/dnf
 
# Copy your code and set working directory
WORKDIR ${LAMBDA_TASK_ROOT}
COPY . ${LAMBDA_TASK_ROOT}
 
# Upgrade pip and install Python dependencies (preferring wheels)
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt
 
# Upgrade urllib3 to a fixed version (without adding to requirements)
RUN pip install --no-cache-dir --upgrade urllib3==2.6.0
 
# Set the CMD to your handler
CMD ["main.lambda_handler"]