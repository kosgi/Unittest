#!/usr/bin/python
'''
 Description:
  Ansible module to parse bsavms list and change the user info to below string format:
  <attuid>|<sudo_perm>|<sshkey#1>|<sshkey#2>|...|<sshkey#n>;<attuid>|
        <sudo_perm>|<ssh_key#1>|<ssh_key#2>|...|<ssh_key#n>;...
'''

import traceback
import os
import yaml
from ansible.module_utils.basic import AnsibleModule

BSAVMS_LIST = {
    "bsavms": {"required": False, "type": "list"}
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

def search_user_item(lu, grp_content, global_content):
    ''' Method to get the actual users list from global file (all.yaml) or group file '''
    ret=[]
    if lu in grp_content.keys():
        ret=grp_content[lu]
    elif lu in global_content.keys():
        ret=global_content[lu]

    return ret

def get_users_from_group_file(grp_fn, grp_fld):
    ''' Method to read the users list defined in group file'''
    yaml.add_multi_constructor('', default_constructor, Loader=yaml.SafeLoader)
    yaml.add_representer(GenericScalar, GenericScalar.to_yaml, Dumper=yaml.SafeDumper)

    # read the group file content
    grp_file = os.path.join(os.getcwd(), 'group_vars', str(grp_fn+'.yaml'))
    grp_obj = open(grp_file, "r")
    grp_content = yaml.safe_load(grp_obj)

    # read global file all.yaml
    glob_file = os.path.join(os.getcwd(), 'group_vars', 'all.yaml')
    glob_obj = open(glob_file, "r")
    glob_content = yaml.safe_load(glob_obj)

    new_lst_users=[]
    for sc, s in enumerate(grp_content[grp_fld], 0):
        usr_item = s[s.find("{")+2:s.find("}")].strip()
        usr_content = search_user_item(usr_item, grp_content, glob_content)
        if not usr_content:
            raise ValueError('user list cannot be empty:[%s]' % (usr_item))
        for uc in usr_content:
            new_lst_users.append(uc)

    grp_obj.close()
    glob_obj.close()
    return new_lst_users

def parse_bsavms(bsavms):
    ''' Method to parse bsavms data and convert users info in list into string '''
    user_flds = ['users_from_group_file', 'users']
    for vm_info in bsavms:
        for fld in user_flds:
            if fld in vm_info.keys():
                if not vm_info[fld]:
                    raise ValueError('[%s] value cannot be empty in %s' % (fld, vm_info))
                elif fld == 'users':
                    # convert the user info into string
                    ufg_str = convert_ui_str(vm_info[fld])

                    # update the users field value
                    vm_info[fld] = ufg_str
                elif fld == 'users_from_group_file':
                    # get the users content from the group file
                    ufg_yaml = get_users_from_group_file(vm_info[fld].strip(), user_flds[1])

                    # convert the users list into string
                    ufg_str = convert_ui_str(ufg_yaml)

                    # add new field users and delete users_from_group_file
                    vm_info[user_flds[1]] = ufg_str
                else:
                    pass

                break
    return bsavms

def validate_bsavms(bsavms):
    ''' Method to validate bsavms data '''
    req_fields = ['name', 'last_octet', 'conf', 'present']
    for vm_data in bsavms:
        for fld in req_fields:
            if fld not in vm_data.keys():
                raise ValueError('mandatory field [%s] missing in %s' % (fld, vm_data))

            if not str(vm_data[fld]).strip():
                raise ValueError('mandatory field [%s] value cannot be empty [%s]' % (fld, vm_data))

def convert_ui_str(userinfo):
    ''' Method to parse users data '''
    ui_fields = ['name', 'sudo', 'key']
    state_fld = 'state'
    str_userinfo = ""
    for uic, uikv in enumerate(userinfo, 1):
        if state_fld not in uikv:
            raise ValueError('mandatory field [%s] missing in %s' % (state_fld, uikv))

        if not uikv[state_fld]:
            raise ValueError('[%s] field cannot be empty in %s' % (state_fld, uikv))

        if uikv[state_fld].strip() != 'present':
            continue

        for fldc, fld in enumerate(ui_fields, 1):
            if fldc == 1:
                # get 'name' field
                if fld not in uikv:
                    raise ValueError('mandatory field [%s] missing in %s' % (fld, uikv))

                # make sure that the name is not empty
                userid = uikv[fld]
                if not userid:
                    raise ValueError('[%s] field cannot be empty in %s' % (fld, uikv))

                str_userinfo += userid.strip()
                str_userinfo += '|'
            if fldc == 2:
                # get 'sudo' field. Set it to False, if missing
                sudo_perm = False
                if fld in uikv and uikv[fld] and uikv[fld].strip() == 'present':
                    sudo_perm = True

                str_userinfo += str(sudo_perm)
                str_userinfo += '|'
            if fldc == len(ui_fields):
                # get the ssh key and append as string
                if fld not in uikv:
                    raise ValueError('mandatory field [%s] missing in %s' % (fld, uikv))

                # make sure that ssh keys are defined
                if not uikv[fld]:
                    raise ValueError('[%s] field cannot be empty in %s' % (fld, uikv))

                for keyc, key in enumerate(uikv[fld], 1):
                    kfp = os.path.join(os.getcwd(), 'sshkeys', str(key.strip()))
                    with open(kfp, "r") as kfo:
                        str_userinfo += kfo.read().replace('\n', '')
                    if keyc != len(uikv[fld]):
                        str_userinfo += '|'
        if uic != len(userinfo):
            str_userinfo += ';'

    return str_userinfo

def main():
    ''' Method to read bsavms list from Ansible and parse it '''
    module = AnsibleModule(argument_spec=BSAVMS_LIST, supports_check_mode=True)
    errorcode = 0
    try:
        bsavms_list = module.params['bsavms']
        if not bsavms_list:
            errorcode = 2
            raise ValueError("'bsavms' list cannot be empty.")
        else:
            validate_bsavms(bsavms_list)
            res = parse_bsavms(bsavms_list)
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
