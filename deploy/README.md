# Deploying this Project

## Deploying to an Ubuntu machine

Get Ansible, which we use for deploying to the machine:

```bash
brew install ansible
```

First, install Python on the machine so you can use Ansible
to run remote commands.  This installs both Python 2 (for
supporting Ansible 2.0 commands), and Python 3 (for
installation in the virutal environment that's going to be
running the server).

```bash
ansible -i hosts isitdead.today --user ubuntu --sudo -m raw \
  -a "apt-get -y update && apt-get install -y python-minimal python3"
```

Then use this convenience script to deploy the project using
Ansible:

```bash
./deploy
```

To see the available tags, type `./deploy --tags=help`.

You need an `aws-credentials.json` file to run the full
deploy scripts.  You also need to `ssh-add` a keypair that
lets you access the AWS instance through ssh.  Talk to one
of the project administrators for access to both the
credentials JSON file and the AWS keypair.

## Getting the SSL certificates

Following [these
directions](https://certbot.eff.org/#ubuntuxenial-nginx),
install standalone certificates.  They should look like this
on Ubuntu 16.04:

```bash
# Install certbot
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:certbot/certbot
sudo apt-get update
sudo apt-get install certbot 

# Download certificates
sudo certbot certonly --standalone \
  -d isitdead.today \
  -d isitalive.today \
  -d www.isitdead.today \
  -d www.isitalive.today
```

Upload the certificates to the AWS S3 `isitdead` bucket.
One way to do this is to copy these files to your local
machine using Ansible, and then uploading them to S3.

```bash
# Copy the files from server to your machine:
ansible -i hosts isitdead.today --user ubuntu --sudo -m fetch \
  -a "src=/etc/letsencrypt/live/isitdead.today/fullchain.pem dest=./nginx.crt flat=yes"
ansible -i hosts isitdead.today --user ubuntu --sudo -m fetch \
  -a "src=/etc/letsencrypt/live/isitdead.today/privkey.pem dest=./nginx.key flat=yes"
```

Then just use the
[S3 GUI](https://console.aws.amazon.com/s3/) to upload both
of these files to the `isitdead` bucket.  Ask one of the
project maintainers to access for the AWS account for
managing this bucket.

Note: this might be needlessly complex, and there may be
ways of generating the `fullchain.pem` and `privkey.pem`
files in a way that doesn't require you to need to fetch
them from the AWS instance, but just lets you dump them
directly into the S3 bucket.

## Debugging Unexpected Server Behavior

SSH into the machine:

```bash
ssh ubuntu@isitdead.today
```

Take a look at the logs for the `isitdead` process that
`supervisorctl` has been keeping.

```bash
sudo cat /var/log/supervisor/isitdead-stderr*
sudo cat /var/log/supervisor/isitdead-stdout*
```
