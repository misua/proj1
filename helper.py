from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

 def create_vm():
        # Set your Azure subscription ID and resource group name
        subscription_id = 'YOUR_SUBSCRIPTION_ID'
        resource_group_name = 'YOUR_RESOURCE_GROUP_NAME'

        # Set your AKS cluster name and virtual network name
        aks_cluster_name = 'YOUR_AKS_CLUSTER_NAME'
        virtual_network_name = 'YOUR_VIRTUAL_NETWORK_NAME'

        # Set your VM name, size, and OS image details
        vm_name = 'YOUR_VM_NAME'
        vm_size = 'Standard_B2s'
        os_image = 'Canonical:UbuntuServer:18.04-LTS:latest'

        # Create the Azure SDK clients
        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        network_client = NetworkManagementClient(credential, subscription_id)
        resource_client = ResourceManagementClient(credential, subscription_id)

        # Get the AKS cluster resource ID
        aks_cluster = resource_client.resources.get_by_id(resource_group_name, 'Microsoft.ContainerService/managedClusters', aks_cluster_name)

        # Get the virtual network resource ID
        virtual_network = resource_client.resources.get_by_id(resource_group_name, 'Microsoft.Network/virtualNetworks', virtual_network_name)

        # Create the VM
        vm_parameters = {
            'location': aks_cluster.location,
            'hardware_profile': {
                'vm_size': vm_size
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': os_image.split(':')[0],
                    'offer': os_image.split(':')[1],
                    'sku': os_image.split(':')[2],
                    'version': os_image.split(':')[3]
                }
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': network_client.virtual_network_peerings.get(resource_group_name, virtual_network_name, 'peerName').remote_virtual_network.id
                }]
            }
        }

        vm = compute_client.virtual_machines.create_or_update(resource_group_name, vm_name, vm_parameters)

        # Wait for the network interfaces to be ready
        network_interfaces = compute_client.virtual_machines.list_network_interfaces(resource_group_name, vm_name)
        for network_interface in network_interfaces:
            compute_client.virtual_machines.begin_create_or_update(resource_group_name, vm_name, vm_parameters).wait()

    # Call the create_vm() function in __main__.py or any other module
    if __name__ == '__main__':
        create_vm()
