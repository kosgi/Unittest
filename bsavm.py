#!/usr/bin/python
'''
 This library module is for calling bsavm on a remote host to manage virtual machines.
 This yaml file calls the help function on the remote machine:
- hosts: all
  become: true
  tasks:
  - name: Test help
    bsavm:
        help: True
        simulate: True
    register: result

  - debug: var=result

This yaml script simulates creating a virtual machine on the remote host:
- hosts: all
  become: true
  tasks:
  - name: Test calling bsavm_noop.sh
    bsavm:
        last_octet: "99"
        name: LoLCat
        conf: "small_mgt.conf"
        pass: "password1234"
        shell: |+
            echo Hello World
            echo Saluton Mondo
            echo Hola Mundo
        simulate: True
        present: True
    register: result

  - debug: var=result

This yaml script simulates deleting a virtual machine on the remote host:
- hosts: all
  become: true
  tasks:
  - name: Test calling bsavm_noop.sh
    bsavm:
        name: LoLCat
        simulate: True
        present: False
    register: result

  - debug: var=result
'''

from __future__ import print_function
import traceback
from subprocess import Popen, PIPE, CalledProcessError
import unittest
from ansible.module_utils.basic import AnsibleModule

CLIENT_SIDE_BSAVM = 'bsavm.sh'

BSAVM_NO_CHANGE = 96

BSAVM_PARAMS_DICT = {
    'help': {'default': False, 'type': 'bool'}, # -h
    'last_octet': {'required': False, 'type': 'str'}, # -i
    'name': {'required': False, 'type': 'str'}, # -n
    'conf': {'required': False, 'type': 'str'}, # -f
    'pass': {'required': False, 'type': 'str', 'no_log': True}, # -w
    'external_ip': {'required': False, 'type': 'str'}, # -e
    'present': {'required': False, 'type': 'bool'}, # -f
    'shell': {'required': False, 'type': 'str'}, # -s
    'users': {'required': False, 'type': 'str'}, # -u
    'simulate': {'required': False, 'type': 'bool'}
}

BSAVM_PARAMS_SET = set()

def get_bsavm_params_set():
    '''
    This function initializes BSAVM_PARAMS_SET if it is empty. It then returns BSAVM_PARAMS_SET
    '''
    if not BSAVM_PARAMS_SET:
        for k in BSAVM_PARAMS_DICT:
            BSAVM_PARAMS_SET.add(k)
    return BSAVM_PARAMS_SET


def get_from_dict_else_fail(varname, params, fail_message):
    '''
    This function returns the value params[varname]
    and raises an exception if varname is not in params
    '''
    if varname in params and params[varname] is not None:
        return params[varname]
    raise ValueError(fail_message)


def is_none(string):
    '''Boolean function that returns True if string is like None or like the empty string'''
    return string is None or string == '' or string == 'None'


def make_command(params):
    '''
    This function takes the dict of parameter returned from AnsibileModule and makes a list
    of parameters which can be passed to Popen.
    '''
    good_params = get_bsavm_params_set()
    test_params = set(params.keys())
    bad_params = test_params - good_params
    if len(bad_params) > 0:
        unknown_keys = str(bad_params)
        raise ValueError('unkown params in make_command, %s' % unknown_keys)

    simulate = params['simulate'] if  'simulate' in params else False

    client_side_bsavm = '/opt/bsa/bin/noop_bsavm.py' if simulate else '/opt/bsa/bin/' + \
          CLIENT_SIDE_BSAVM

    cmd = [client_side_bsavm]

    if 'help' in params and params['help']:
        cmd.append('-h')
        return cmd

    present = get_from_dict_else_fail('present', params, 'present must be in parameters')

    name = get_from_dict_else_fail('name', params, 'name must be in parameters')

    if present is False:
        cmd += ['-d', params['name']]
    else:
        last_octet = get_from_dict_else_fail( \
                        'last_octet', params, \
                        'last_octet must be specified if present is True')

        conf = get_from_dict_else_fail( \
                        'conf', params, \
                        'conf must be specified if present is True')

        cmd += ['-i', last_octet, '-n', name, '-f', conf]

        #parse optional parameters
        if 'pass' in params and not is_none(params['pass']):
            cmd += ['-w', params['pass']]
        if 'external_ip' in params and not is_none(params['external_ip']):
            cmd += ['-e', params['external_ip']]
        if 'shell' in params and not is_none(params['shell']):
            cmd += ['-s', params['shell']]
        if 'users' in params and not is_none(params['users']):
            cmd += ['-u']
            cmd += ["'" + params['users'] + "'"]
    return cmd


class TestCommand(unittest.TestCase):
    '''
    This class test the function make_command..
    '''
    client_side_bsavm = '/opt/bsa/bin/' + CLIENT_SIDE_BSAVM
    def test1(self):
        '''
        Test fully specified VM.
        '''
        params = {'last_octet': 99, 'name': 'LoLCat', 'conf': 'kitten.cfg',
                  'pass': 'ICanHazCheezburger', 'external_ip': '216.176.177.64',
                  'shell': 'echo hello world', 'present': True}
        cmd = make_command(params)
        expected = [self.client_side_bsavm, '-i', 99, '-n', 'LoLCat',
                    '-f', 'kitten.cfg', '-w', 'ICanHazCheezburger', '-e',
                    '216.176.177.64', '-s', 'echo hello world']
        self.assertEqual(expected, cmd)

    def test1a(self):
        '''
        Test fully specified VM simulation mode.
        '''
        params = {'last_octet': 99, 'name': 'LoLCat', 'conf': 'kitten.cfg',
                  'pass': 'ICanHazCheezburger', 'external_ip': '216.176.177.64',
                  'shell': 'echo hello world', 'present': True, 'simulate': True}
        cmd = make_command(params)
        expected = ['/opt/bsa/bin/noop_bsavm.py', '-i', 99, '-n', 'LoLCat',
                    '-f', 'kitten.cfg', '-w', 'ICanHazCheezburger', '-e',
                    '216.176.177.64', '-s', 'echo hello world']
        self.assertEqual(expected, cmd)

    def test1b(self):
        '''
        Test fully specified VM without external IP.
        '''
        params = {'last_octet': 99, 'name': 'LoLCat', 'conf': 'kitten.cfg',
                  'pass': 'ICanHazCheezburger', 'external_ip': 'None',
                  'shell': 'None', 'present': True}
        cmd = make_command(params)
        expected = [self.client_side_bsavm, '-i', 99, '-n', 'LoLCat',
                    '-f', 'kitten.cfg', '-w', 'ICanHazCheezburger']
        self.assertEqual(expected, cmd)

    def test2(self):
        '''
        Test deleting a VM.
        '''
        params = {'name': 'LoLCat', 'present': False}
        cmd = make_command(params)
        expected = [self.client_side_bsavm, '-d', 'LoLCat']
        self.assertEqual(expected, cmd)

    def test2a(self):
        '''
        Test deleting a VM in simulation mode.
        '''
        params = {'name': 'LoLCat', 'present': False, 'simulate': True}
        cmd = make_command(params)
        expected = ['/opt/bsa/bin/noop_bsavm.py', '-d', 'LoLCat']
        self.assertEqual(expected, cmd)

    def test3(self):
        '''
        Test calling help.
        '''
        params = {'help': True}
        cmd = make_command(params)
        expected = [self.client_side_bsavm, '-h']
        self.assertEqual(expected, cmd)

    def test3a(self):
        '''
        Test calling help in simulation mode.
        '''
        params = {'help': True, 'simulate': True}
        cmd = make_command(params)
        expected = ['/opt/bsa/bin/noop_bsavm.py', '-h']
        self.assertEqual(expected, cmd)

def ansible_main():
    '''
    This function interfaces into Ansible.
    '''
    module = AnsibleModule(argument_spec=BSAVM_PARAMS_DICT)
    try:
        module.log('starting module bsavm')
        module.log('module.params = {}'.format(module.params))
        cmd = make_command(module.params)
        module.log('cmd = {}'.format(cmd))
        strcmd = ' '.join(cmd)
        module.log('strcmd = {}'.format(strcmd))

        try:
            module.log('calling Popen')
            proc = Popen(cmd, stdin=None, stdout=PIPE, stderr=PIPE)
            module.log('Popen, finished')
            result, error = proc.communicate()
            module.log('Popen result = {}'.format(result))
            module.log('Popen error = {}'.format(error))
            errorcode = proc.returncode
            module.log('Popen returncode = {}'.format(errorcode))
        except CalledProcessError as xcptn:
            errmsg = '%s failed: output = %s, error code = %s\n' % \
                     (strcmd, xcptn.output, xcptn.returncode)
            module.warn('{} failed'.format(strcmd))
            module.warn(str(xcptn))
            module.warn('stacktrace = {' + str(traceback.format_exc()) + '}')
            module.fail_json(msg=errmsg)
        except Exception, xcptn:
            errmsg = str(xcptn)
            module.warn(errmsg)
            module.warn('stacktrace = {' + str(traceback.format_exc()) + '}')
            module.fail_json(msg=errmsg)
        else:
            effective_errorcode = 0 if errorcode == BSAVM_NO_CHANGE else errorcode
            response = {
                'bsavm_stdout': result,
                'bsavm_stderr': error,
                'bsavm_returncode': effective_errorcode,
                'command': strcmd}
            localchanged = True if errorcode == 0 else False
            module.log('bsavm finished')
            module.exit_json(changed=localchanged, meta=response)
        #call module.fail_json if there was an error
    except Exception, xcptn:
        errmsg = str(xcptn) + 'stacktrace = {' + str(traceback.format_exc()) + '}'
        module.warn(str(xcptn))
        module.warn('stacktrace = {' + str(traceback.format_exc()) + '}')
        module.fail_json(msg=errmsg)


if __name__ == '__main__':
    ansible_main()
