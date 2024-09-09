# Cool ThreeFold Pulumi Python


This repo contains some ~arguably~ awesome examples of how to use ThreeFold's Pulumi provider with Python. These examples specifically focus on use of Python to achieve some additional automation aside from the creation of the deployment.

Please note that these examples are not meant to be "production ready". For instance, running shell scripts on the remote machine after deployment is a primitive way to complete post deployment machine setup. There are better ways, such as baking the setup steps into an image or using a dedicated post deployment provisioning tool.

Disclaimer aside, the methods demonstrated in this repository can be especially useful for testing and prototyping.

## Prerequisits

You'll need:

* pulumi
* python3 (with venv module)


## Setup

Our approach here will be to install the ThreeFold Pulumi Python module into a virtual environment, along with the generic Pulumi module. For convenience, you can use one venv a the root of the repo with these basic dependencies.

If any subprojects have specific dependencies, it might be wiser to use a separate venv for each one.

Here's the basic steps:

```
mkdir venv
python3 -m venv venv
source venv/bin/activate # Use appropriate file for your shell
pip install -r requirements.txt
```

## Running a project

These projects use a vars.py file to hold the seed phrase to use for deployment, the network to deploy to, and sometimes other info. A template is provided to work from:

```
cd project
cp vars.py.template vars.py
nano vars.py
```

Write in your values then save and exit. Now you can try bringing up the deployment:

```
pulumi login --local
pulumi up
```

Managing stacks is up to you. Using one per project doesn't hurt.
