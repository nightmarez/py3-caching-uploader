# -*- coding: utf-8 -*-
import os
from pathlib import Path
import paramiko
from paramiko import SSHClient
from scp import SCPClient
import hashlib
import json

def md5(name: str) -> str:
	hash_md5 = hashlib.md5()

	with open(name, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)

	return hash_md5.hexdigest()

def check_file_changes(name: str) -> bool:
	my_file = Path(CACHE_FILES)

	if not my_file.is_file():
		f = open(CACHE_FILES, "w+")
		f.close()

	f = open(CACHE_FILES, "r")
	lines = []

	while True:
		line = f.readline()

		if not line:
			f.close()
			break

		lines.append(line)

	need_load = False
	found = False
	curr_hash = False

	f = open(CACHE_FILES, "w")
	for line in lines:
		pair = line.split('|')
		file_name = pair[0]
		file_hash = pair[1].strip()

		if file_name == name:
			found = True
			curr_hash = md5(file_name)

			if curr_hash != file_hash:
				line = file_name + '|' + curr_hash + '\r\n'
				need_load = True

		f.write(line)

	if not found:
		need_load = True
		curr_hash = md5(name)
		line = name + '|' + curr_hash + '\r\n'
		f.write(line)

	f.close()

	return need_load

def need_create_dir(name: str) -> bool:
	my_file = Path(CACHE_DIRS)

	if not my_file.is_file():
		f = open(CACHE_DIRS, "w+")
		f.close()

	f = open(CACHE_DIRS, "r")
	lines = []

	while True:
		line = f.readline()

		if not line:
			f.close()
			break

		lines.append(line)

	found = False
	f = open(CACHE_DIRS, "w")
	for line in lines:
		if line.strip() == name:
			found = True

		f.write(line.strip() + '\r\n')

	if not found:
		f.write(name + '\r\n')

	return not found

def need_upload_file(name: str) -> bool:
	ext = name.split('.')
	ext = ext[len(ext) - 1]

	if ext in ['php', 'css', 'js', 'png', 'jpg', 'gif', 'sql', 'svg', 'htaccess', 'txt', 'xml']:
		return True

	return False

def upload_file(name: str, path: str, scp: SCPClient):
	if check_file_changes(name):
		print("File '" + name + "' uploading...")
		scp.put(name, path)
	else:
		print("File '" + name + "' skip")

def upload_directory(name: str, ssh: SSHClient, scp: SCPClient, recursive: bool = True):
	print("Observe '" + name + "' directory...")

	if name != '.' and need_create_dir(name):
		ssh.exec_command('mkdir -p ' + SERVER_DIRECTORY + '/' + name)

	files = [f for f in os.listdir(name) if os.path.isfile(name + '/' + f)]
	for f in files:
		if need_upload_file(f):
			upload_file(name + '/' + f, SERVER_DIRECTORY + '/' + name, scp)

	if recursive:
		dirs = [d for d in os.listdir(name) if os.path.isdir(name + '/' + d)]
		for d in dirs:
			if d not in ['.', '..', '.git', '__pycache__']:
				upload_directory(name + '/' + d, ssh, scp)

def load_config_rules(data, ssh: SSHClient, scp: SCPClient):
	directories_rules = data['directories']

	for directory_rule in directories_rules:
		directory_path = directory_rule[0]
		is_recursive = directory_rule[1] if len(directory_rule) > 1 else True
		upload_directory(directory_path, ssh, scp, is_recursive)

	files_rules = data['files']

	for file_rule in files_rules:
		file_name = file_rule[0]
		destination_path = file_rule[1] if len(file_rule) > 1 else '.'
		upload_file(file_name, destination_path, scp)

def load_config_cache(data):
	global CACHE_FILES
	global CACHE_DIRS

	CACHE_FILES = data['directories']
	CACHE_DIRS = data['files']

def load_config_server(data):
	global SERVER_IP
	global SERVER_USERNAME
	global SERVER_PASSWORD
	global SERVER_DIRECTORY

	SERVER_IP = data['ip']
	SERVER_USERNAME = data['user']
	SERVER_PASSWORD = data['pass']
	SERVER_DIRECTORY = data['directory']

def load_config(before, after):
	with open('uploader-config.json', 'r') as file:
		data = json.loads(file.read())
		server_data = data['server']
		cache_data = data['cache']
		rules_data = data['rules']

		load_config_server(server_data)
		load_config_cache(cache_data)
		(ssh, scp) = before()

		try:
			load_config_rules(rules_data, ssh, scp)
		finally:
			after(ssh, scp)

def init_ssh():
	ssh = SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(SERVER_IP, 22, SERVER_USERNAME, SERVER_PASSWORD)
	scp = SCPClient(ssh.get_transport())
	return (ssh, scp)

def close_ssh(ssh: SSHClient, scp: SCPClient):
	scp.close()
	ssh.close()

def upload():
	load_config(init_ssh, close_ssh)

if __name__ == "__main__":
	upload()
