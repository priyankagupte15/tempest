# Copyright 2014 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from tempest.api.workloadmgr import base
from tempest import config
from tempest import test
import json
import sys
from tempest import api
from oslo_log import log as logging
from tempest.common import waiters
from tempest import tvaultconf
import time
LOG = logging.getLogger(__name__)
CONF = config.CONF


class WorkloadsTest(base.BaseWorkloadmgrTest):

    credentials = ['primary']

    @classmethod
    def setup_clients(cls):
        super(WorkloadsTest, cls).setup_clients()
        cls.client = cls.os.wlm_client

    @test.attr(type='smoke')
    @test.idempotent_id('9fe07175-912e-49a5-a629-5f52eeada4c2')
    def test_2_data_integrity(self):
        self.total_workloads=1
        self.vms_per_workload=2
        self.volume_size=1
        self.workload_instances = []
        self.workload_volumes = []
        self.workloads = []
        self.full_snapshots = []
        self.md5sums_dir_before = {}
        self.md5sums_dir_after = {}
        self.incr_snapshots = []
        self.restores = []
        self.fingerprint = ""
        self.vm_details_list = []
        self.original_fingerprint = ""
        self.vms_details = []

        self.original_fingerprint = self.create_key_pair(tvaultconf.key_pair_name)
        # floating_ips_list = self.get_floating_ips()
        for vm in range(0,self.vms_per_workload):
             vm_name = "tempest_test_vm_" + str(vm+1)
             vm_id = self.create_vm(vm_name)
             self.workload_instances.append(vm_id)
             volume_id1 = self.create_volume(self.volume_size,tvaultconf.volume_type)
             volume_id2 = self.create_volume(self.volume_size,tvaultconf.volume_type)
             self.workload_volumes.append(volume_id1)
             self.workload_volumes.append(volume_id2)
             self.attach_volume(volume_id1, vm_id, device="/dev/vdb")
             self.attach_volume(volume_id2, vm_id,device="/dev/vdc")

        for id in range(len(self.workload_instances)):
            floating_ip = self.get_floating_ips()[0]
            self.set_floating_ip(str(floating_ip), self.workload_instances[id])
            ssh = self.SshRemoteMachineConnectionWithRSAKey(floating_ips_list[id])
            self.execute_command_disk_create(ssh, floating_ips_list[id])
            self.execute_command_disk_mount(ssh, floating_ips_list[id])
    # #
    # #     # before restore
        self.vm_details_list = []
        for id in range(len(self.workload_instances)):
            self.vm_details_list.append(self.get_vm_details(self.workload_instances[id]))

        for id in range(len(self.workload_instances)):
            self.vms_details.append(self.get_vms_details_list(id, self.vm_details_list))

        LOG.debug("vm details list before backups" + str( self.vm_details_list))
        LOG.debug("vm details dir before backups" + str( self.vms_details))

        self.md5sums_dir_before = self.data_populate_before_backup(self.workload_instances, floating_ips_list, 100, 6)
    #
    # #     # create workload, take backup
        self.workload_id=self.workload_create(self.workload_instances,tvaultconf.parallel)
        self.snapshot_id=self.workload_snapshot(self.workload_id, True)
        self.wait_for_workload_tobe_available(self.workload_id)
        self.assertEqual(self.getSnapshotStatus(self.workload_id, self.snapshot_id), "available")
	self.workload_reset(self.workload_id)

        self.md5sums_dir_before = self.data_populate_before_backup(self.workload_instances, floating_ips_list, 100, 7)

        self.snapshot_id=self.workload_snapshot(self.workload_id, False)
        self.wait_for_workload_tobe_available(self.workload_id)
        self.assertEqual(self.getSnapshotStatus(self.workload_id, self.snapshot_id), "available")
	self.workload_reset(self.workload_id)
        time.sleep(40)

        self.delete_vms(self.workload_instances)


        if tvaultconf.restored_instance_flavor == 3:
            vcpus = 2
            ram = 4096
            disk = 40
        int_net_1_name = self.get_net_name(tvaultconf.int_net_1_id)
        LOG.debug("int_net_1_name" + str(int_net_1_name))
        int_net_2_name = self.get_net_name(tvaultconf.int_net_2_id)
        LOG.debug("int_net_2_name" + str(int_net_2_name))
        int_net_1_subnets = self.get_subnet_id(tvaultconf.int_net_1_id)
        LOG.debug("int_net_1_subnet" + str(int_net_1_subnets))
        int_net_2_subnets = self.get_subnet_id(tvaultconf.int_net_2_id)
        LOG.debug("int_net_2_subnet" + str(int_net_2_subnets))

        self.restore_id=self.snapshot_selective_restore(self.workload_id, self.snapshot_id,restore_name = tvaultconf.restore_name,
                                                        instance_id = self.workload_instances,
                                                        to_restore_instance_1 = True,
                                                        to_restore_instance_2 = True,
                                                        vcpus = vcpus,
                                                        ram = ram,
                                                        disk = disk,
                                                        int_net_1_id = tvaultconf.int_net_1_id,
                                                        int_net_2_id = tvaultconf.int_net_2_id,
                                                        int_net_1_name = int_net_1_name,
                                                        int_net_2_name = int_net_2_name,
                                                        int_net_1_subnets = int_net_1_subnets,
                                                        int_net_2_subnets = int_net_2_subnets)
        self.wait_for_snapshot_tobe_available(self.workload_id, self.snapshot_id)
        self.assertEqual(self.getRestoreStatus(self.workload_id, self.snapshot_id, self.restore_id), "available","Workload_id: "+self.workload_id+" Snapshot_id: "+self.snapshot_id+" Restore id: "+self.restore_id)

        # after selective restore_id and incremental change
        # after restore
        self.vm_list = []
        # restored_vm_details = ""
        self.restored_vm_details_list = []
        self.vm_list  =  self.get_restored_vm_list(self.restore_id)
        LOG.debug("Restored vms : " + str (self.vm_list))


        for id in range(len(self.vm_list)):
            self.restored_vm_details_list.append(self.get_vm_details(self.vm_list[id]))
        LOG.debug("Restored vm details list after incremental change " + str(self.restored_vm_details_list))
        internal_network_name = self.get_net_name(tvaultconf.int_net_2_id)

        self.vms_details_after_one_click_restore = []
        for id in range(len(self.vm_list)):
            self.vms_details_after_one_click_restore.append(self.get_vms_details_list(id, self.restored_vm_details_list))

        for vms in range(len(self.vm_list)):
            for item in self.vms_details_after_one_click_restore[vms]:
                if item.split()[1] == "flavor":
                    self.assertTrue(item.split()[2] == "3", "After one click restore flavor not matched")
                elif item.split()[1] == "internal":
                    self.assertTrue(item.split()[3] == internal_network_name , "After one click restore Network not matched")

        self.md5sums_dir_after = self.calculate_md5_after_restore(self.vm_list, floating_ips_list)

        for id in range(len(self.vm_list)):
            self.assertTrue(self.md5sums_dir_before[str(floating_ips_list[id])]==self.md5sums_dir_after[str(floating_ips_list[id])], "md5sum verification unsuccessful for ip" + str(floating_ips_list_after_restore[id]))
