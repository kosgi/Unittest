# This script will process a list of user documents
# and does following operations
# 1. merge different types of users lists
# 2. Create Users
# 3. Grant sudo permission
# 4. Verify whether user exists
# 5. Add SSH authorized keys for user
# 6. Add SSH authorized keys for root

import yaml
import subprocess

class user_op:

    def run_cmd(self,cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
        if output:
            output = output.strip().decode("utf-8")
        if error:
            error = error.decode("utf-8")
        if p.returncode != 0:
            print(error)
            #raise Exception("Error")
        return output

    # Create Users
    def user_add(self, username):
        cmd = ["useradd", username]
        return self.run_cmd(cmd)

    # Grant sudo permission
    def user_add_sudo(self , username, user_dir=None):
        cmd = ["usermod", "-a", "-G" , username]
        return self.run_cmd(cmd)

    # Verify whether user exists
    def user_verify( self, username):
        ps = subprocess.Popen(('getent', 'passwd', username), stdout=subprocess.PIPE)
        output, error = ps.communicate()
        if output:
            output = output.strip().decode("utf-8")
        if error :
            error = error.decode("utf-8")
        if username in output :
            print("user is present")
        return output

    # Add SSH authorized keys for user
    def add_authorised_key(self, key_file):
        cmd = ["cat", key_file, ">>", "~/.ssh/authorized_keys"]
        return self.run_cmd(cmd)

    #Add SSH authorized keys for root user
    def add_root_authorised_key(self, key_file):
        cmd = ["cat", key_file, ">>", "/root/.ssh/authorized_keys"]
        return self.run_cmd(cmd)

def main():
    keys_path = '/home/sk3798/bootstrap/ansible/sshkeys/'
    with open("/home/sk3798/bootstrap/ansible/group_vars/all.yaml", "r") as stream:
        try:
            users_list = []
            user_ops = user_op()
            data = yaml.safe_load(stream)

            #merge users lists
            for item in data:
                if 'dev_users' in item or 'sys_admin_users' in item or 'alimas_users' in item:
                    for i in data[item] :
                        users_list.append(i)

#            print(user_dict)
            for user_dict in users_list:
                if 'present' == user_dict['state']:
                    #add the user
                    user_ops.user_add(user_dict['name'])

                    #grant sudo permission
                    if 'present' == user_dict['sudo']:
                        user_ops.user_add_sudo(user_dict['name'])

                    #verify whether user exists
                    user_ops.user_verify(user_dict['name'])

                    #add SSH authorized key
                    for item in user_dict['key']:
                        user_ops.add_authorised_key(keys_path + item)

                    #add id_rsa_bsa.pub key to the root user's authorized_keys
                    user_ops.add_root_authorised_key(keys_path + 'id_rsa_bsa.pub')

                    #add id_rsa_bsa.pub key to the bsa user's authorized_keys
                    user_ops.add_authorised_key(keys_path + 'id_rsa_bsa.pub')

        except yaml.YAMLError as exc:
            print(exc)

if __name__ == "__main__":
    main()
