# utils.py
from django.conf import settings
from twilio.rest import Client
import paramiko
import os
import subprocess

def send_sms_notification(to_phone, message_body):
    """
    Sends an SMS to the specified phone number using Twilio.
    :param to_phone: str -> phone number in E.164 format, e.g. +919876543210
    :param message_body: str -> The text message
    """
    # print(to_phone)
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    client = Client(account_sid, auth_token)
    client.messages.create(
        body=message_body,
        from_=from_phone,
        to=to_phone
    )



RUNNING_SCRIPTS = {}

def ssh_run_script(ip, username, password, script_path, use_venv=True, venv_path=None):
    try:
        ssh = paramiko.SSHClient()
        # WARNING: AutoAddPolicy trusts unknown hosts. For production,
        # use RejectPolicy with a known_hosts file:
        #   ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        #   ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        ssh.connect(ip, username=username, password=password)

        # Get the directory and file name of the script
        script_dir = os.path.dirname(script_path)
        script_name = os.path.basename(script_path)
        
        # Determine activation command if a virtual environment is to be used
        if use_venv:
            if not venv_path:
                venv_path = f'C:/Users/{username}/Documents/PROJECTS/AIInvigilator/susenv/Scripts/activate.bat'
            activation_cmd = f'call "{venv_path}" && '
        else:
            activation_cmd = ""
        
        # Build the command using proper quoting; use cmd /c so the shell exits after execution
        command = f'cmd /c "cd /d \"{script_dir}\" && {activation_cmd}python \"{script_name}\""'
        
        # Open a session with a pseudo-terminal; this allows us to send Ctrl+C later.
        channel = ssh.get_transport().open_session()
        channel.get_pty()
        channel.exec_command(command)
        
        # Optionally, you can start a thread to read output asynchronously.
        # For now, we just store the SSH client and channel in our global dictionary.
        key = f"{username}_{script_name}"
        RUNNING_SCRIPTS[key] = {
            "mode": "remote",
            "ssh": ssh,
            "channel": channel
        }
        print(f"\n[{username}] Remote script {script_name} started.")
        return True, "Remote script started successfully."
    except Exception as e:
        return False, str(e)


# Whitelist of allowed ML scripts that can be executed
ALLOWED_SCRIPTS = {
    'front.py', 'top_corner.py', 'hand_raise.py', 'leaning.py',
    'passing_paper.py', 'mobile_detection.py', 'hybrid_detector.py',
    'process_uploaded_video.py', 'process_uploaded_video_stream.py',
}

def local_run_script(script_path):
    try:
        # Get the directory and file name from the script_path
        script_dir = os.path.dirname(os.path.abspath(script_path))
        script_name = os.path.basename(script_path)

        # Validate script name against whitelist to prevent command injection
        if script_name not in ALLOWED_SCRIPTS:
            return False, f"Script '{script_name}' is not in the allowed scripts list."

        # Use list form (no shell=True) to prevent command injection
        process = subprocess.Popen(
            ['python', script_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=script_dir,
            text=True
        )

        key = f"local_{script_name}"
        RUNNING_SCRIPTS[key] = {
            "mode": "local",
            "process": process
        }
        print(f"[Local] Script {script_name} started.")
        return True, "Local script started successfully."
    except Exception as e:
        return False, str(e)  


