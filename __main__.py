#!/usr/bin/env python3

import pulumi
from pulumi_azuread import Application, ServicePrincipal, ServicePrincipalPassword
from pulumi_azure import core, containerservice,compute,storage
from pulumi_kubernetes import Provider
from pulumi_kubernetes.autoscaling.v1 import HorizontalPodAutoscaler
from pulumi_kubernetes.apps.v1 import Deployment
from pulumi_kubernetes.core.v1 import PersistentVolume, PersistentVolumeClaim,Service
from pulumi_kubernetes import networking
from pulumi_azure_native.compute import Disk


# Create an Azure Resource Group
resource_group = core.ResourceGroup('myResourceGroup',location='eastus')

# Create an Azure AD application for AKS
app = Application('aks', display_name='aks')

# Create an Azure AD service principal for the application
sp = ServicePrincipal('aksSp', application_id=app.application_id)

# Create an Azure AD service principal password
sp_password = ServicePrincipalPassword('aksSpPassword', service_principal_id=sp.id, value='password', end_date='2099-01-01T00:00:00Z')


cluster = containerservice.KubernetesCluster('myAKSCluster',
    resource_group_name=resource_group.name,
    default_node_pool={
        'name': 'default',
        'node_count': 1,
        'vm_size': 'Standard_B2s',
        'enable_auto_scaling': True,
        'min_count': 1,
        'max_count': 3,
    },
    dns_prefix='myaks',
    linux_profile={
        'adminUsername': 'adminuser',
        'sshKey': {
            'keyData': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDmjIDHPOHhTnYYccEaBgNZJs9P1PJ8kguQsIIHtqniTj51NZ5zwDI7OL0U3Uj1PZRau7Q4F+9hME7KC6BHaGRZ1bFUpvkqO29yAZvpL/SdP1UtKPxc5vIfItRGYUgeMoeYJLOg7zdU+naKuIqYmKoybf7BSlLxRLTv+2uzpzeb+2u2oDqvMeaf1MagfQYQ5pZJrzMzytsjZlQomEk4tcLW6vvnETjFlP7I8FtW4fq5mwIIKCoOFI0IzwCLjjayzErsC6yODfsojxu6Vxpb1ZvG1sNe6WNcbfK0hf/xSiCqB1Yvna+g9Vjy8R88R9kTfS3uBjdBD2XZN1v3GegKm/Pwuey4O16WnI9tSAVIcjeTpZj4ooiws1aOCmAMhi9aWyDedlLs/a7b2GkKquK29A8xxNx1CJq9qg2tcWdROmUt5OzMmzv85ueI9X6tjQ0ijv4xX3eqh6GLRwXXPJS2OwJKbhBvm/OZHm0CQ8YlPdtvR0VTLpRl5lOVo65icsZ1zj+kkt9EzCLMjUM+DXUp2BrFptYygrzQjPhcAR0ef7qDoG6gp5cm8xZjM+T2D0oouQxvGhLpWp9yRgHqwc5t8FwMWVKmzGG8KHcaoOglirq8rIXnrSROcbs2JnTSqXVSnxIEXPzQ0VxFY40ozDzgnS70F4p9cU3hNSYRK5obie0OhQ== char.lice@outlook.com'
        },
    },
    service_principal={
        'clientId': app.application_id,
        'clientSecret': sp_password.value,
    },
)

# Export the kubeconfig
pulumi.export('kubeconfig', cluster.kube_config_raw)

# Create a Kubernetes provider instance that uses our new AKS cluster.
k8s_provider = Provider('k8sProvider', kubeconfig=cluster.kube_config_raw)

# Create a Kubernetes Horizontal Pod Autoscaler
hpa = HorizontalPodAutoscaler('myHPA',
    metadata={'name': 'myhpa'},
    spec={
        'scaleTargetRef': {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'name': 'myapp',
        },
        'minReplicas': 1,
        'maxReplicas': 5,
        'metrics': [
            {
                'type': 'Resource',
                'resource': {
                    'name': 'cpu',
                    'targetAverageUtilization': 70,
                },
            },
            {
                'type': 'Resource',
                'resource': {
                    'name': 'memory',
                    'targetAverageUtilization': 80,
                },
            },
        ],
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)


# Export the kubeconfig
pulumi.export('kubeconfig', cluster.kube_config_raw)


# Create a Storage Account
storage_account = storage.Account('mystorageccount',
    resource_group_name=resource_group.name,
    account_tier='Standard',
    account_replication_type='LRS'
)

# Create a Disk
disk = Disk('myDisk',
    resource_group_name=resource_group.name,
    creation_data={
        'create_option': 'Empty'
    },
    disk_size_gb=2
)

# Use disk.name and disk.id in pv diskName and diskURI
pv = PersistentVolume('myPV',
    metadata={
        'name': 'my-pv',
    },
    spec={
        'capacity': {
            'storage': '2Gi',
        },
        'accessModes': ['ReadWriteOnce'],
        'persistentVolumeReclaimPolicy': 'Retain',
        'azureDisk': {
            'diskName': disk.name,
            'diskURI': disk.id,
            'kind': 'Managed',
            'cachingMode': 'None',
            'fsType': 'ext4',
        },
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)


# Create a PersistentVolumeClaim
pvc = PersistentVolumeClaim('myPVC',
    metadata={
        'name': 'my-pvc',
    },
    spec={
        'accessModes': ['ReadWriteOnce'],
        'resources': {
            'requests': {
                'storage': '2Gi',
            },
        },
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create a MySQL Deployment
mysql_deployment = Deployment('mysql',
    metadata={
        'name': 'mysql',
    },
    spec={
        'replicas': 1,
        'selector': {
            'matchLabels': {
                'app': 'mysql',
            },
        },
        'template': {
            'metadata': {
                'labels': {
                    'app': 'mysql',
                },
            },
            'spec': {
                'containers': [{
                    'name': 'mysql',
                    'image': 'mysql:latest',
                    'env': [
                        {
                            'name': 'MYSQL_ROOT_PASSWORD',
                            'value': 'tob0lz',
                        },
                        {
                            'name': 'MYSQL_USER',
                            'value': 'tobolz',
                        },
                        {
                            'name': 'MYSQL_PASSWORD',
                            'value': 'tobolz',
                        },
                        {
                            'name': 'MYSQL_DATABASE',
                            'value': 'wordpress',
                        },
                    ],
                    'ports': [{
                        'containerPort': 3306,
                    }],
                }],
            },
        },
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[pv, pvc])
)


# Create a MySQL Service
mysql_service = Service('mysql',
    metadata={
        'name': 'mysql',
    },
    spec={
        'selector': {
            'app': 'mysql',
        },
        'ports': [{
            'protocol': 'TCP',
            'port': 3306,
            'targetPort': 3306,
        }],
        'type': 'ClusterIP',
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[mysql_deployment])
)

# Modify the WordPress Deployment to use MySQL
wordpress_deployment = Deployment('wordpress',
    metadata={
        'name': 'wordpress',
    },
    spec={
        'replicas': 1,
        'selector': {
            'matchLabels': {
                'app': 'wordpress',
            },
        },
        'template': {
            'metadata': {
                'labels': {
                    'app': 'wordpress',
                },
            },
            'spec': {
                'containers': [{
                    'name': 'wordpress',
                    'image': 'wordpress:latest',
                    'ports': [{
                        'containerPort': 80,
                    }],
                    'env': [
                        {
                            'name': 'WORDPRESS_DB_HOST',
                            'value': 'mysql',
                        },
                        {
                            'name': 'WORDPRESS_DB_USER',
                            'value': 'tobolz',
                        },
                        {
                            'name': 'WORDPRESS_DB_PASSWORD',
                            'value': 'tobolz',
                        },
                        {
                            'name': 'WORDPRESS_DB_NAME',
                            'value': 'wordpress',
                        },
                    ],
                    'volumeMounts': [{
                        'name': 'html-volume',
                        'mountPath': '/var/www/html',
                    }],
                }],
                'volumes': [{
                    'name': 'html-volume',
                    'persistentVolumeClaim': {
                        'claimName': 'my-pvc',
                    },
                }],
            },
        },
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)


# Create a Service for WordPress
wordpress_service = Service('wordpress-service',
    metadata={
        'name': 'wordpress-service',
    },
    spec={
        'selector': {
            'app': 'wordpress',
        },
        'ports': [{
            'protocol': 'TCP',
            'port': 80,
            'targetPort': 80,
        }],
        'type': 'LoadBalancer',
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[wordpress_deployment])
)

# Create an Ingress for WordPress
ingress = networking.v1.Ingress('wordpress-ingress',
    metadata={
        'name': 'wordpress-ingress',
    },
    spec={
        'rules': [{
            'host': 'wordpress.example.com',
            'http': {
                'paths': [{
                    'path': '/',
                    'pathType': 'Prefix',
                    'backend': {
                        'service': {
                            'name': 'wordpress',
                            'port': {
                                'number': 80,
                            },
                        },
                    },
                }],
            },
        }],
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[wordpress_service])
)
# Output the public IP
#pulumi.export('public_ip', wordpress_service.status['loadBalancer']['ingress'][0]['ip'])
# Assuming wordpress_service is your Service object
load_balancer = wordpress_service.status.apply(lambda status: status.load_balancer)
public_ip = load_balancer.apply(lambda lb: lb.ingress[0].ip if lb.ingress else None)
pulumi.export('public_ip', public_ip)


