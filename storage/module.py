# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import socket
from mgr_module import MgrModule, MgrStandbyModule
from cherrypy.wsgiserver import CherryPyWSGIServer 
from cherrypy.wsgiserver.ssl_builtin import BuiltinSSLAdapter

from storage.openapi_connector import create_openapi_application



class AppStub(object):
    def __init__(self, module):
        self.module = module

    def __call__(self, environ, start_response):

        self.module.log.info('Entered AppStub.__call__()')    

        status = '200 OK'
        output = 'Hello World!\n'
        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]


class PluginCommon(object):
    # This class provides functionality common to both
    # active and standby instances of the service

    OPTS_AND_DEFAULTS = [
        {'name': 'listen_port',    'default_value': '8888'   },
        {'name': 'use_ssl',        'default_value': 'False'  },
        {'name': 'crt_file',       'default_value': None     },
        {'name': 'key_file',       'default_value': None     },
        {'name': 's3_user',        'default_value': 'admin'  },
        {'name': 's3_access_key',  'default_value': None     },
        {'name': 's3_secret_key',  'default_value': None     },
        {'name': 's3_admin_url',   'default_value': 'admin'  }
    ]

    def __init__(self):
       self.plugin_conf = {}
       self.server = None
       self.url = ''

    def load_options(self, child_module):
        for opt in self.OPTS_AND_DEFAULTS:
            self.plugin_conf[opt['name']] = child_module.get_config(opt['name'], opt['default_value'])

        child_module.log.info('Got the following options: {}'.format(json.dumps(self.plugin_conf))) 

    def create_server(self, app):
        if self.plugin_conf['use_ssl'] in ['true', 'True', 'TRUE', 'yes', 'Yes', 'YES']:
            if self.plugin_conf['crt_file'] == None or self.plugin_conf['key_file'] == None:
                return
            protocol = 'https'
        else: 
            protocol = 'http'

        self.url = '{}://{}:{}'.format(protocol, socket.getfqdn(),
                                                 self.plugin_conf['listen_port'])
        self.server = CherryPyWSGIServer((socket.getfqdn(),
                                          int(self.plugin_conf['listen_port'])), app)

        if protocol == 'https':
            self.server.ssl_adapter = BuiltinSSLAdapter(self.plugin_conf['crt_file'],
                                                        self.plugin_conf['key_file'])
    
class Module(MgrModule, PluginCommon):

    # OPTIONS list and COMMANDS list for integration with ceph

    OPTIONS = []
    for opt in PluginCommon.OPTS_AND_DEFAULTS:
        OPTIONS.append({'name': opt['name']})

    COMMANDS = [
        {
            'cmd': 'storage set-option '
                   'name=option_name,type=CephString '
                   'name=option_value,type=CephString',
            'desc': 'Set storage plugin option, e.g. \'ceph storage set-option listen_port 80\'',
            'perm': 'w'
        },
        {
            'cmd': 'storage list-options',
            'desc': 'List all storage plugin options, stored in ceph configuration db',
            'perm': 'r'
        },
        {
            'cmd': 'storage list-active-options',
            'desc': 'List all storage plugin options currently used',
            'perm': 'r'
        },
        {
            'cmd': 'storage inspect',
            'desc': 'List data',
            'perm': 'r'
        },
        {
            'cmd': 'storage help',
            'desc': 'Print usage',
            'perm': 'r'
        },
        {
            'cmd': 'storage',
            'desc': 'Print usage',
            'perm': 'r'
        }
    ]

    def __init__(self, *args, **kwargs):
        MgrModule.__init__(self, *args, **kwargs)
        PluginCommon.__init__(self)

    def serve(self):

        self.log.info('Entered Module.serve()')

        self.load_options(self)
        self.app = create_openapi_application()
        self.log.info('About to create the WSGI server...')

        self.create_server(self.app)

        if self.server != None:
            self.log.info('Saving active URL "{}" and starting server'.format(self.url))
            self.set_uri(self.url)
            self.server.start()
        else:
            self.log.error('Something went wrong... Server instance was not created.')

    def shutdown(self):
        self.log.info('Shutdown entered, stopping server...')
        self.server.stop()

    def handle_command(self, inbuf, command):

        self.log.info('Entered handle_command() method with the following command: {}'.format(json.dumps(command)))

        if command['prefix'] == 'storage set-option':
           if {'name': command['option_name']} in self.OPTIONS :
               self.set_config(command['option_name'], command['option_value'])
               return (0,
                       'Option "' +
                        command['option_name'] +
                        '" was set to "' +
                        command['option_value'] + '".',
                        '')
           return (-1, '', 'Invalid option "{0}"'.format(command['option_name']))

        elif command['prefix'] == 'storage list-options':
            out={}
            for opt in self.OPTIONS:
                out[opt['name']] = self.get_config(opt['name'])
            return (0, json.dumps(out, indent = 4), '')

        elif command['prefix'] == 'storage list-active-options':
            return (0, json.dumps(self.plugin_conf, indent = 4),'')

        elif command['prefix'] == 'storage help' or command['prefix'] == 'storage':
            return (0,
                    'Implemented_storage_commands:\n' +
                    json.dumps(self.COMMANDS, indent=4),
                    '')
        elif command['prefix'] == 'storage inspect':
            id = self.get_mgr_id()
            return (0,
                    json.dumps(self.get('mgr_map'), indent=4),
                    '')
        else:
            return (-1, '', 'Invalid command "{0}", try "ceph storage help", '.format(command['prefix']))


class AppRedirect(object):
    def __init__(self, module):
        self.standby_module = module

    def __call__(self, environ, start_response):

        status = '303 See Other'
        url = self.standby_module.get_active_uri()

        self.standby_module.log.info('Redirecting from standby to active {}'.format(url))

        output = 'This resource can be found at <a href=\'{}\'>{}</a>'.format(url, url)
        response_headers = [('Content-type', 'text/plain'),
                            ('Location', url),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]

class StandbyModule(MgrStandbyModule, PluginCommon):

    def __init__(self, *args, **kwargs):
        MgrStandbyModule.__init__(self, *args, **kwargs)
        PluginCommon.__init__(self)

    def serve(self):

        self.log.info('Entered StandbyModule.serve()')

        self.load_options(self)
        self.app = AppRedirect(self)

        self.log.info('About to create the WSGI standby server')

        self.create_server(self.app)
        if self.server != None:
            self.log.info('Starting standby server...')
            self.server.start()
        else:
            self.log.error('Something went wrong... Server instance was not created.')

    def shutdown(self):
        self.log.info('Shutdown entered, stopping server...')
        self.server.stop()


