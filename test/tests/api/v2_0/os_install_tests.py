from config.api1_1_config import *
from config.settings import *
from modules.logger import Log
from workflows_tests import WorkflowsTests as workflows
from proboscis import test
from proboscis import after_class
from proboscis import before_class
from proboscis.asserts import fail
from json import loads
import os
from on_http_api2_0 import ApiApi as Api
from modules.amqp import AMQPWorker
from modules.worker import WorkerThread
from proboscis.asserts import assert_equal

LOG = Log(__name__)
DEFAULT_TIMEOUT = 5400
ENABLE_FORMAT_DRIVE=False
if os.getenv('RACKHD_ENABLE_FORMAT_DRIVE', 'false') == 'true': 
    ENABLE_FORMAT_DRIVE=True

@test(groups=['os-install.v1.1.tests'], \
    depends_on_groups=['amqp.tests'])
class OSInstallTests(object):

    def __init__(self):
        self.__client = config.api_client
        self.__base = defaults.get('RACKHD_BASE_REPO_URL', \
            'http://{0}:{1}'.format(HOST_IP, HOST_PORT))
        self.__obm_options = { 
            'obmServiceName': defaults.get('RACKHD_GLOBAL_OBM_SERVICE_NAME', \
                'ipmi-obm-service')
    }

    @before_class()
    def setup(self):
        pass
        
    @after_class(always_run=True)
    def teardown(self):
        self.__format_drives()  
    
    def __get_data(self):
        return loads(self.__client.last_response.data)
    
    def __post_workflow(self, graph_name, nodes, body):
        self.post_workflows(graph_name, timeout_sec=DEFAULT_TIMEOUT, nodes=nodes, data=body)

# cped code
    def post_workflows(self, graph_name, \
                       timeout_sec=300, nodes=[], data={}, \
                       tasks=[], callback=None, run_now=True):
        self.__graph_name = graph_name
        self.__graph_status = []

        if len(nodes) == 0:
            Api().nodes_get_all()
            for n in loads(self.__client.last_response.data):
                if n.get('type') == 'compute':
                    nodes.append(n.get('id'))

        if callback == None:
            callback = self.handle_graph_finish

        for node in nodes:
            LOG.info('Starting AMQP listener for node {0}'.format(node))
            worker = AMQPWorker(queue=QUEUE_GRAPH_FINISH, callbacks=[callback])
            thread = WorkerThread(worker, node)
            self.__tasks.append(thread)
            tasks.append(thread)

            try:
        #      #  Nodes().nodes_identifier_workflows_active_delete(node)
         #     # not sure if passing in cancel action correctly
                Api().nodes_workflow_action_by_id(node, action="cancel")
            except Exception, e:
                assert_equal(HTTP_NOT_FOUND, e.status, \
                             message='status should be {0}'.format(HTTP_NOT_FOUND))

            retries = 5
        #    Nodes().nodes_identifier_workflows_active_get(node)
            Api().nodes_get_workflow_by_id(node, active=True)
            status = self.__client.last_response.status
            while status != HTTP_NO_CONTENT and retries != 0:
                status = self.__client.last_response.status
                LOG.warning('Workflow status for Node {0} (status={1},retries={2})' \
                            .format(node, status, retries))
                sleep(1)
                retries -= 1
          #      Nodes().nodes_identifier_workflows_active_get(node)
                Api().nodes_get_workflow_by_id(node, active=True)

            assert_equal(HTTP_NO_CONTENT, status, \
                         message='status should be {0}'.format(HTTP_NO_CONTENT))
     #       Nodes().nodes_identifier_workflows_post(node, name=graph_name, body=data)
            Api().nodes_post_workflow_by_id(node, name=graph_name, body=data)
        if run_now:
            self.run_workflow_tasks(self.__tasks, timeout_sec)

    def __format_drives(self):
        # Clear disk MBR and partitions
        command = 'for disk in `lsblk | grep disk | awk \'{print $1}\'`; do '
        command = command + 'sudo dd if=/dev/zero of=/dev/$disk bs=512 count=1 ; done'
        body = {
            'options': {
                'shell-commands': {
                    'commands': [ 
                        { 'command': command } 
                    ]
                },
                'set-boot-pxe': self.__obm_options,
                'reboot-start': self.__obm_options,
                'reboot-end': self.__obm_options
            }
        }
        self.__post_workflow('Graph.ShellCommands', [], body) 

    @test(enabled=ENABLE_FORMAT_DRIVE, groups=['format-drives.v1.1.test'])
    def test_format_drives(self):
        """ Drive Format Test """
        self.__format_drives()  
        
    def install_centos(self, version, nodes=[], options=None):
        graph_name = 'Graph.InstallCentOS'
        os_repo = defaults.get('RACKHD_CENTOS_REPO_PATH', \
            self.__base + '/repo/centos/{0}'.format(version))
        body = options
        if body == None:
            body = {
                'options': {
                    'defaults': {
                        'installDisk': '/dev/sda',
                        'version': version,
                        'repo': os_repo,
			'users': [{ 'name': 'onrack', 'password': 'Onr@ck1!', 'uid': 1010 }]
                    },
                    'set-boot-pxe': self.__obm_options,
                    'reboot': self.__obm_options,
                    'install-os': {
                        'schedulerOverrides': {
                            'timeout': 3600000
                        }
                    }
                }
            } 
        self.__post_workflow(graph_name, nodes, body)
        
    def install_esxi(self, version, nodes=[], options=None):
        graph_name = 'Graph.InstallESXi'
        os_repo = defaults.get('RACKHD_ESXI_REPO_PATH', \
            self.__base + '/repo/esxi/{0}'.format(version))
        body = options
        if body == None:
            body = {
                'options': {
                    'defaults': {
                        'installDisk': 'firstdisk',
                        'version': version, 
                        'repo': os_repo,
                        'users': [{ 'name': 'onrack', 'password': 'Onr@ck1!', 'uid': 1010 }]
                    },
                    'set-boot-pxe': self.__obm_options,
                    'reboot': self.__obm_options,
                    'install-os': {
                        'schedulerOverrides': {
                            'timeout': 3600000
                        }
                    }
                }
            }
        self.__post_workflow(graph_name, nodes, body)  
        
    def install_suse(self, version, nodes=[], options=None):
        graph_name = 'Graph.InstallSUSE'
        os_repo = defaults.get('RACKHD_SUSE_REPO_PATH', \
            self.__base + '/repo/suse/{0}/'.format(version))
        body = options
        if body == None:
            body = {
                'options': {
                    'defaults': {
                        'installDisk': '/dev/sda',
                        'version': version,
                        'repo': os_repo,
                        'users': [{ 'name': 'onrack', 'password': 'Onr@ck1!', 'uid': 1010 }]
                    },
                    'set-boot-pxe': self.__obm_options,
                    'reboot': self.__obm_options,
                    'install-os': {
                        'schedulerOverrides': {
                            'timeout': 3600000
                        }
                    }
                }
            }
        self.__post_workflow(graph_name, nodes, body)
        
    def install_ubuntu(self, version, nodes=[], options=None):
        graph_name = 'Graph.InstallUbuntu'
        os_repo = defaults.get('RACKHD_UBUNTU_REPO_PATH', \
            self.__base + '/repo/ubuntu')
        body = options
        if body == None:
            body = {
                'options': {
                    'defaults': {
                        'installDisk': '/dev/sda',
                        'version': version,
                        'repo': os_repo,
                        'baseUrl':'install/netboot/ubuntu-installer/amd64',
                        'kargs':{
                            'live-installer/net-image': os_repo + '/install/filesystem.squashfs'
                        },
                        'users': [{ 'name': 'onrack', 'password': 'Onr@ck1!', 'uid': 1010 }]
                    },
                    'set-boot-pxe': self.__obm_options,
                    'reboot': self.__obm_options,
                    'install-ubuntu': {
                        'schedulerOverrides': {
                            'timeout': 3600000
                        }
                    }
                }
            }
        self.__post_workflow(graph_name, nodes, body)
    
    def install_windowsServer2012(self, version, nodes=[], options=None):
        graph_name = 'Graph.InstallWindowsServer'
        os_repo = defaults.get('RACKHD_SMB_WINDOWS_REPO_PATH', None)
        if None == os_repo:
            fail('user must set RACKHD_SMB_WINDOWS_REPO_PATH')
        body = options
        if body == None:
        # The value of the productkey below is not a valid product key. It is a KMS client key that was generated to run the workflows without requiring a real product key. This key is 
        # available to public on the Microsoft site.
            body = {
                'options': {
                    'defaults': {
                        'productkey': 'D2N9P-3P6X9-2R39C-7RTCD-MDVJX',
                        'smbUser':  defaults.get('RACKHD_SMB_USER' , 'onrack'),
                        'smbPassword':  defaults.get('RACKHD_SMB_PASSWORD' , 'onrack'),
                        'completionUri': 'winpe-kickstart.ps1',
                        'smbRepo': os_repo,
                        'repo' : defaults.get('RACKHD_WINPE_REPO_PATH',  \
                            self.__base + '/repo/winpe')
                    },
                    'firstboot-callback-uri-wait':{
                        'completionUri': 'renasar-ansible.pub'
                    }
                }
            }
        self.__post_workflow(graph_name, nodes, body)

    @test(enabled=True, groups=['centos-6-5-install.v1.1.test'])
    def test_install_centos_6(self):
        """ Testing CentOS 6.5 Installer Workflow """
        self.install_centos('6.5')
        
    @test(enabled=True, groups=['centos-7-install.v1.1.test'])
    def test_install_centos_7(self, nodes=[], options=None):
        """ Testing CentOS 7 Installer Workflow """
        self.install_centos('7.0')

    @test(enabled=True, groups=['ubuntu-install.v1.1.test'])
    def test_install_ubuntu(self, nodes=[], options=None):
        """ Testing Ubuntu 14.04 Installer Workflow """
        self.install_ubuntu('trusty')
       
    @test(enabled=True, groups=['suse-install.v1.1.test'])
    def test_install_suse(self, nodes=[], options=None):
        """ Testing OpenSuse Leap 42.1 Installer Workflow """
        self.install_suse('42.1')
        
    @test(enabled=True, groups=['esxi-5-5-install.v1.1.test'])
    def test_install_esxi_5_5(self, nodes=[], options=None):
        """ Testing ESXi 5.5 Installer Workflow """
        self.install_esxi('5.5')
        
    @test(enabled=True, groups=['esxi-6-install.v1.1.test'])
    def test_install_esxi_6(self, nodes=[], options=None):
        """ Testing ESXi 6 Installer Workflow """
        self.install_esxi('6.0')
        
    @test(enabled=True, groups=['windowsServer2012-install.v1.1.test'])
    def test_install_windowsServer2012(self, nodes=[], options=None):
        """ Testing Windows Server 2012 Installer Workflow """
        self.install_windowsServer2012('10.40') 

