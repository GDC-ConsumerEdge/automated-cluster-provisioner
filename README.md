# GDC Connected Cluster Provisioner

This solution automates the provisioning and configuration of Google Distributed Cloud connected clusters at scale during pre staging processes as edge zones are turned up. 

## Table of Contents
- [GDC Connected Cluster Provisioner](#gdc-connected-cluster-provisioner)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [High Level Architecture - Cluster Creation](#high-level-architecture---cluster-creation)
    - [High Level Architecture - Cluster Modification](#high-level-architecture---cluster-modification)
      - [Supported Modifications](#supported-modifications)
  - [Pre-Requisites](#pre-requisites)
    - [Required Roles for Terraform Agent](#required-roles-for-terraform-agent)
    - [Cluster Intent Git PAT Token](#cluster-intent-git-pat-token)
    - [ConfigSync](#configsync)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Cluster Intent](#cluster-intent)
    - [Cluster Intent Data Format](#cluster-intent-data-format)
    - [Cluster Intent Validation](#cluster-intent-validation)
  - [Operations](#operations)
    - [Metrics](#metrics)
    - [Alerts](#alerts)
    - [Automated Retries](#automated-retries)
  - [Terraform Details](#terraform-details)
    - [Providers](#providers)
    - [Modules](#modules)
    - [Inputs](#inputs)
    - [Outputs](#outputs)
  - [Disclaimer](#disclaimer)

## Overview

The GDC connected cluster provisioner solution is automation which optimizes for:

- **Declared Intent**. Cluster parameters should be specified well ahead of when the cluster can be provisioned. Clusters parameters should be able to be defined months in advanced with cluster creation happening once the Edge Zone is available.
- **Safety**. By design, errors should not result in fleet wide impact. We do this by preferring manual remediation over automated. Once a cluster is created, there are only a few supported update actions and no supported delete operations.
- **End to end automation**: With preconfigured declared intent, we design the automation to run without any human intervention. 
- **Extensibility**. This solution is an opinionated deployment pipeline and will not cover 100% of provisioning workflows or GCP environment requirements. Extension of the provisioning logic is expected.

### High Level Architecture - Cluster Creation
![High Level Architecture](./docs/automated%20cluster%20provisioner.png)

- **Zone Watcher**: A Cloud Function which polls against the Cluster Intent Data and the available Edge Zones. If there is a declared cluster for a new zone, it will kick off Cloud Build to provision the cluster. Otherwise, it will skip. 
- **Edge Zone**: There are 2 GDC APIs which are leveraged to detect the availability of an Edge Zone
  - The [Zone](https://cloud.google.com/distributed-cloud/edge/latest/docs/reference/hardware/rest/v1alpha/projects.locations.zones#Zone) created as part of an order. This provides the `globallyUniqueId` or edge zone node location for use during cluster provisioning as well as the `state` of the zone. 
  -  The available [machines](https://cloud.google.com/distributed-cloud/edge/latest/docs/reference/container/rest/v1/projects.locations.machines) in a given GCP project. This is used to determine whether a cluster is already running on a set of machines or not through the `hostedNode` property. If a cluster is already provisioned, it will not trigger provisioning.
-  **Cluster Intent Data**: A CSV file which holds the parameters necessary for cluster creation. Example: [example-source-of-truth.csv](./example-source-of-truth.csv)
-  **Cloud Build Job**: This is a bash script which queries the cluster intent database to read the necessary parameter to create a cluster, bootstrap configsync and other fleet services, and validate the completion of the provisioning process.

### High Level Architecture - Cluster Modification

![High Level Architecture](./docs/automated%20cluster%20provisioner%20modified.png)

- **Cluster Watcher**: A Cloud Function which polls against the Cluster Intent Data and the available clusters. If there are any supported modifications that need to be made, it will kick off the Cloud Build job.
- **GDC Clusters**: The GDC Cluster resource. The Cloud watcher function queries against this api to compare parameters against the cluster intent data while the cloud build job will call the appropriate update commands to modify the cluster.
-  **Cluster Intent Data**: A CSV file which holds the parameters necessary for cluster creation. Example: [example-source-of-truth.csv](./example-source-of-truth.csv)
-  **Cloud Build Job**: This is a bash script which queries the cluster intent database to read the necessary parameters to modify the cluster.
  
#### Supported Modifications

By design, the solution does not support destructive operations across the fleet. Beyond cluster creation, these are the supported actions:

- Adding new VLANs
- Updating the maintenance window, or removing the maintenance window
- Updating the maintenance exclusion window(s), or removing the maintenance exclusion windows.

Other modifications not listed like deleting a VLAN, or reconfiguring ConfigSync should be scripted outside of this solution. 

## Pre-Requisites
The solution is designed to run within a GCP organization. It is expected that the user will have the following:

- A GCP project to host the solution resources.
- A GCP project to host the GDC clusters.
- A GCP project to host the GDC machines.
- A git repository containing the cluster intent data.
- A git token to authenticate with the git repository.
- Adequate permissions to deploy the GCP resources from terraform.

### Required Roles for Terraform Agent
| GCP Role Name | Projects |
|---------------|---------|
| roles/cloudbuild.builds.editor | Main |
| roles/cloudfunctions.admin | Main |
| roles/cloudscheduler.admin | Main|
| roles/iam.serviceAccountAdmin | Main |
| roles/resourcemanager.projectIamAdmin | All |
| roles/iam.serviceAccountUser | Main
| roles/serviceusage.serviceUsageAdmin | All|
| roles/storage.admin | Main |


### Cluster Intent Git PAT Token
When using Github, a personal access token must be created and uploaded to Secret Manager. When using Gitlab, a project access token must be configured and uploaded to Secret Manager. The automated cluster provisioning solution uses these tokens to query against the cluster intent data, which is a CSV file stored in a git repository.

### ConfigSync
This project assumes the usage of [ConfigSync](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/overview) for handling declared cluster configuration and any necessary workload configuration in the pre-staging environment.

## Installation
```
cd bootstrap

cp terraform.tfvars.example terraform.tfvars
# update the terraform.tfvars as needed

terraform init -backend-config=env/prod.gcs.tfbackend 
terraform plan
terraform apply -var="environment=prod"
```

This will deploy all the GCP resources for the automated cluster provisioning solution. Use the `environment=...` terraform variable to separate out multiple instances of the solution. For example, having separated dev vs. prod instances is helpful to validate and ensure any development doesn't disrupt active provisioning.

## Usage

With the Automated Cluster Provisioning (ACP) solution, users can provision clusters on their GDC Edge Zones by setting cluster parameters in a cluster intent CSV file and having the ACP solution trigger provisioning once the edge zone is prepared and online. An example of cluster intent can be found [here](./example-source-of-truth.csv), where each row is one cluster for a store location.

> [!IMPORTANT]  
> The Cluster Intent CSV file is set up and managed by the user. It is not stored or managed by Google. 

The expected sequence to order a GDC Edge Zone with a provisioned cluster would be:

1) In a GCP project, place an [order](https://cloud.google.com/distributed-cloud/edge/latest/docs/order) through the UI or API.  
   - This will generate a [Zone](https://cloud.google.com/distributed-cloud/edge/latest/docs/reference/hardware/rest/v1alpha/projects.locations.zones/get) resource which is used for status tracking.
2) Fill out the Cluster Intent CSV
   - Add a new line into the Cluster Intent CSV file filling out `store_id`, `machine_project_id`, and `location` as the key to find the appropriate edge zone. Then fill out all the other required parameters in the CSV file.
3) Wait for your cluster to be provisioned.
   - While your hardware is being fulfilled, the ACP solution continuously polls for the Zone's state property to determine if the edge zone is ready for provisioning. Once ready, it will create a cluster using the parameters defined in the Cluster Intent CSV file. No manual action required. 
4) The Edge Zone is now ready for delivery. 


## Cluster Intent

### Cluster Intent Data Format

| Parameter                                 | Required | Description                                                                                                                                                                                                                   |
|-------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| store_id                                  | yes      | This is the same as the order's zone name. It is used to look up state and the corresponding EdgeContainer Zone.                                                                                                              |
| zone_name                                 | no       | (Optional.) In situations where there is no order placed, or when one wants to bypass the gdc hardware management api logic, you can specify the zone_name here which will skip all api calls to the hardware management api. |
| machine_project_id                        | yes      | The GCP project that hosts the edge zone.                                                                                                                                                                                     |
| fleet_project_id                          | yes      | The GCP project that will host the cluster.                                                                                                                                                                                   |
| cluster_name                              | yes      | The name of the cluster.                                                                                                                                                                                                      |
| location                                  | yes      | The GCP region. Note that this has to be the same region that the order was placed in. Order region == Edge Zone region == Cluster region.                                                                                    |
| node_count                                | yes      | The number of nodes in a cluster                                                                                                                                                                                              |
| cluster_ipv4_cidr                         | yes      | The desired IPv4 CIDR block for Kubernetes pods.                                                                                                                                                                              |
| services_ipv4_cidr                        | yes      | The desired IPv4 CIDR block for Kubernetes services.                                                                                                                                                                          |
| external_load_balancer_ipv4_address_pools | yes      | The desired IPv4 CIDR block for ingress traffic of GDC load balancers.                                                                                                                                                        |
| sync_repo                                 | yes      | The git repository used for ConfigSync's RootSync object.                                                                                                                                                                     |
| sync_branch                               | yes      | The branch used for ConfigSync's RootSync object.                                                                                                                                                                             |
| sync_dir                                  | yes      | The path within the repository used for ConfigSync's RootSync object.                                                                                                                                                         |
| git_token_secrets_manager_name            | yes      | Secrets Manager secret for the git PAT token to deploy into the cluster for ConfigSync to pull github configuration                                                                                                           |
| cluster_version                           | yes      | Initial cluster version to provision the cluster                                                                                                                                                                              |
| maintenance_window_start                  | no       | (Optional.) Start time of the MW                                                                                                                                                                                              |
| maintenance_window_end                    | no       | (Optional.) End time of the MW                                                                                                                                                                                                |
| maintenance_window_recurrence             | no       | (Optional.) Frequency of the MW                                                                                                                                                                                               |
| maintenance_exclusion_name_1              | no       | (Optional.) Name of maintenance exclusion window. Supports up to 3 exclusion windows by specifying additional columns `maintenance_exclusion_name_2` and `maintenance_exclusion_name_3`                                       |
| maintenance_exclusion_start_1             | no       | (Optional.) Start of maintenance exclusion window. Supports up to 3 exclusion windows by specifying additional columns `maintenance_exclusion_start_2` and `maintenance_exclusion_start_3`                                    |
| maintenance_exclusion_end_1               | no       | (Optional.) End of maintenance exclusion window. Supports up to 3 exclusion windows by specifying additional columns `maintenance_exclusion_end_2` and `maintenance_exclusion_end_3`                                          |
| subnet_vlans                              | no       | This is used in the cluster provisioning automation to call the edge network API to create a VLANs for a particular edge-zone                                                                                                 |
| recreate_on_delete                        | yes      | Whether to recreate a cluster with a zone state of `ACTIVE`. This can be used for automated re-provisioning (delete the cluster and it'll automatically re-create).                                                           |

### Cluster Intent Validation

We recommend that cluster intent is validated as part of the PR process for proper format and values. There are a number of validation tools available, and we provide an example validation github action that uses the [csv-validator](https://github.com/GDC-ConsumerEdge/csv-validator) tool. For more information, view the [validation model](./validation/cluster_intent.py) and the [validation github action](./.github/workflows/validate_sot.yaml)

## Operations

### Metrics

This table describes the metrics available to monitor cluster provisioning.

| Name                                    | Type  | Tags         | Description                                                                     |
| --------------------------------------- | ----- | ------------ | ------------------------------------------------------------------------------- |
| unknown-zones-${environment}            | Count | zone         | Zones found in the environment, but are not specified as part of cluster intent |
| ready-stores-${environment}             | Count | store_id     | Store edge zones ready for provisioning                                         |
| cluster-creation-success-${environment} | Count | cluster_name | Cluster Creation Success Count                                                  |
| cluster-creation-failure-${environment} | Count | cluster_name | Cluster Creation Failure Count                                                  |
| cluster-modify-success-${environment}   | Count | cluster_name | Cluster Modify Success Count                                                    |
| cluster-modify-failure-${environment}   | Count | cluster_name | Cluster Modify Failure Count                                                    |

### Alerts

This table describes the alerts created to monitoring cluster provisioning. These alerts are intended to be examples and should be tuned for your environment.

| Name                     | Description                                                                                                          |
|--------------------------|----------------------------------------------------------------------------------------------------------------------|
| unknown-zone-alert       | Alerts whenever an unknown zone not defined in the cluster intent source of truth has been found in the environment. |
| cluster-creation-failure | Alerts when cluster creation has failed                                                                              |
| cluster-modify-failure   | Alerts when cluster modification has failed                                                                          |

### Automated Retries

Automated retries can be configured to address intermittent build failures. To enable, set the `cluster-creation-max-retries` variable in the terraform to a value greater than 0 but less than 5. The solution tracks the number of failed builds for a zone and will retry them until the number exceeds the specified max retry.

> [!Note]
> If you decrease the number of `cluster-creation-max-retries`, this may impact in-progress builds from properly calling the [zone's signal endpoint](https://cloud.google.com/distributed-cloud/edge/latest/docs/reference/hardware/rest/v1alpha/projects.locations.zones/signal) properly. Be sure to manually check that any failed builds are properly retried. This is not a concern when increasing the value.

### Deployment Patterns

For detailed information on the different ways to deploy and manage the Cluster Provisioner, please see the [Deployment Patterns documentation](./module/README.md).


## Disclaimer

This project is not an official Google project. It is not supported by
Google and Google specifically disclaims all warranties as to its quality,
merchantability, or fitness for a particular purpose.
