#!/usr/bin/python
'''
 Description:
  Ansible module to
  1. merge different types of users lists
  2. Create Users
  3. Grant sudo permission
  4. Verify whether user exists
  5. Add SSH authorized keys for user
  6. Add SSH authorized keys for root
'''

import traceback
import os
import yaml
import subprocess
import pwd
from ansible.module_utils.basic import AnsibleModule

USERS_LIST = {
    "users": {"required": False, "type": "list"},
    "userdata": {"required": False, "type": "dict"}
}

class GenericScalar(object):
    ''' Generic class to handle tags prefixed with exclamation mark(!) '''
    def __init__(self, value, tag, style=None):
        self.value = value
        self.tag = tag
        self.style = style

    @staticmethod
    def to_yaml(dumper, data):
        ''' data is a generic scalar '''
        return dumper.represent_scalar(data.tag, data.value, style=data.style)

def default_constructor(loader, tag_suffix, node):
    ''' Define generic constructor to handle tags prefixed with exclamation mark(!) '''
    if isinstance(node, yaml.ScalarNode):
        return GenericScalar(node.value, tag_suffix, style=node.style)
    else:
        raise NotImplementedError('Node: ' + str(type(node)))

class user_op:

    def run_cmd(self,cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
        if output:
            output = output.strip().decode("utf-8")
        if error:
            error = error.decode("utf-8")
        if p.returncode != 0:
            #print(error)
            raise ValueError("Error" + str(error) + str(output))
        return output

    #check if user exits
    def if_user_exist(self, username):
        usernames = [x[0] for x in pwd.getpwall()]
        if username in usernames:
            return True
        return False

    # Create Users
    def user_add(self, username):
        if self.if_user_exist(username):
            return " user created " + username
        else:
            cmd = ["sudo", "/usr/sbin/useradd", username]
            return self.run_cmd(cmd)

    # Delete Users
    def user_del(self, username):
        cmd = ["/usr/sbin/userdel", "-f" , username]
        return self.run_cmd(cmd)

    # Grant sudo permission
    def user_add_sudo(self , username, user_dir=None):
        cmd = ["/usr/sbin/usermod", "-a", "-G" , username]
        return self.run_cmd(cmd)

    # delete sudo permission
    def user_del_sudo(self , username, user_dir=None):
        cmd = [ "/usr/sbin/userdel", username,  "sudo"]
        return self.run_cmd(cmd)

    # Verify whether user exists
    def user_verify( self, username):
        ps = subprocess.Popen(('/usr/bin/getent', 'passwd', username), stdout=subprocess.PIPE)
        output, error = ps.communicate()
        if output:
            output = output.strip().decode("utf-8")
        if error :
            error = error.decode("utf-8")
        if username in output :
            print("user is present")
        return output

    # Add SSH authorized keys for user
    def add_authorised_key(self, key_name, key_val, key_path ):
        with open('/tmp/'+key_name, 'w') as key_f:
            key_f.write(key_val)
        cmd = ["sudo", "/usr/bin/cat", '/tmp/' + key_name, ">>", key_path ]
        raise ValueError('error' + " ".join(cmd))
        return self.run_cmd(cmd)


def validate_users(users):
    ''' Method to validate users data '''
    req_fields = ['name', 'state', 'sudo', 'key']
    for usr in users:
        for fld in req_fields:
            if fld not in usr.keys():
                raise ValueError('mandatory field [%s] missing in %s' % (fld, usr))

            if not str(usr[fld]).strip():
                raise ValueError('mandatory field [%s] value cannot be empty [%s]' % (fld, usr))

def main():
    ''' Method to process user_list from Ansible '''
    module = AnsibleModule(argument_spec=USERS_LIST, supports_check_mode=True)
    errorcode = 0
    try:
        #users_list = get_users_from_group_file()
        users_list = module.params['users']
        keys_list = module.params['userdata']['key_str']['kestr']
        #keys_list = module.params['userdata']
        bsa_key = 'id_rsa_bsa.pub'
        auth_key_path = "~/.ssh/authorized_keys"
        root_auth_key_path = "/root/.ssh/authorized_keys"

        keys_list = keys_list.split("|")
        #keys_list[0] = keys_list[0].split('\'')[-1]
        #keys_list[-1] = keys_list[-1].split('\'')[0]
        it = iter(keys_list)
        keys_dct = dict(zip(it, it))
        #keys_dct = {keys_list[i]: keys_list[i + 1] for i in range(0, len(keys_list), 2)}

        if not users_list:
            errorcode = 2
            raise ValueError("'users' list cannot be empty.")
        else:
            validate_users(users_list)

        user_ops = user_op()
        #'~/bootstrap/ansible/sshkeys/'
        for user_dict in users_list:
            if 'present' == user_dict['state']:
                #add the user
                #try:
                res = user_ops.user_add(user_dict['name'])
                #except:
                #    pass

                #grant sudo permission
                if 'present' == user_dict['sudo']:
                    try:
                        res += user_ops.user_add_sudo(user_dict['name'])
                    except:
                        pass
                #verify whether user exists
                res += user_ops.user_verify(user_dict['name'])

                #add SSH authorized key
                for item in user_dict['key']:
                    res += user_ops.add_authorised_key(item,keys_dct[item], auth_key_path)

                #add id_rsa_bsa.pub key to the root user's authorized_keys
                res += user_ops.add_authorised_key(bsa_key,keys_dct[bsa_key], root_auth_key_path)

                #add rid_rsa_bsa.pub key to the bsa user's authorized_keys
                res += user_ops.add_authorised_key(bsa_key,keys_dct[bsa_key], auth_key_path)

            elif "absent" == user_dict['state']:
                #Delete the user
                if "absent" == user_dict['sudo']:
                    try:
                        user_ops.user_del_sudo(user_dict['name'])
                    except:
                        pass
                user_ops.user_del(user_dict['name'])

    except ValueError, vearg:
        errmsg = str(vearg) + ' stacktrace = {' + str(traceback.format_exc()) + '}'
        module.fail_json(msg=errmsg)
    except Exception, earg:
        errmsg = str(earg) + ' stacktrace = {' + str(traceback.format_exc()) + '}'
        module.fail_json(msg=errmsg)
    else:
        localchanged = True if errorcode == 0 else False
        module.exit_json(change=localchanged, meta=res)

if __name__ == "__main__":
    main()
