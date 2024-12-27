#!/usr/bin/env python3

import os
import subprocess


def install_s3fs():
    # 更新软件包列表
    subprocess.run(["sudo", "yum", "install", "epel-release"], check=True)
    # 安装 s3fs
    subprocess.run(["sudo", "yum", "install", "s3fs-fuse"], check=True)

def create_password_file(access_key, secret_key):
    # 创建认证用的密码文件
    with open(os.path.expanduser("./.passwd-s3fs"), "w") as f:
        f.write(f"{access_key}:{secret_key}\n")
    # 修改文件权限
    subprocess.run(["chmod", "600", os.path.expanduser("./.passwd-s3fs")], check=True)

def mount_s3_bucket(bucket_name, endpoint, mount_point, cahce_point):

    os.makedirs(mount_point, exist_ok=True)
    os.makedirs(cahce_point, exist_ok=True)

    # umount, remount
    subprocess.run(["sudo", "umount", mount_point], check=False)

    # 挂载存储桶  & 缓存配置
    # https://github.com/s3fs-fuse/s3fs-fuse/blob/b83c2852b8b0698c73d8e7c4b9fd522010e4aa66/src/s3fs_help.cpp#L196
    # s3fs mybucket /path/to/mountpoint -o use_cache=/tmp/cache -o ensure_diskfree=20480(MB)
    "   ensure_diskfree (default 0)\n"
    "      - sets MB to ensure disk free space. This option means the\n"
    "        threshold of free space size on disk which is used for the\n"
    "        cache file by s3fs. s3fs makes file for\n"
    "        downloading, uploading and caching files. If the disk free\n"
    "        space is smaller than this value, s3fs do not use disk space\n"
    "        as possible in exchange for the performance.\n"
    "\n"
    "   free_space_ratio (default=\"10\")\n"
    "      - sets min free space ratio of the disk.\n"
    "      The value of this option can be between 0 and 100. It will control\n"
    "      the size of the cache according to this ratio to ensure that the\n"
    "      idle ratio of the disk is greater than this value.\n"
    "      For example, when the disk space is 50GB, the default value will\n"
    "      ensure that the disk will reserve at least 50GB * 10%% = 5GB of\n"
    "      remaining space.\n"
    "   max_stat_cache_size (default=\"100,000\" entries (about 40MB))\n"
    "      - maximum number of entries in the stat cache, and this maximum is\n"
    "        also treated as the number of symbolic link cache.\n"
    "\n"
    "   stat_cache_expire (default is 900))\n"
    "      - specify expire time (seconds) for entries in the stat cache.\n"
    "        This expire time indicates the time since stat cached. and this\n"
    "        is also set to the expire time of the symbolic link cache.\n"
    "\n"
    "   stat_cache_interval_expire (default is 900)\n"
    "      - specify expire time (seconds) for entries in the stat cache(and\n"
    "        symbolic link cache).\n"
    "      This expire time is based on the time from the last access time\n"
    "      of the stat cache. This option is exclusive with stat_cache_expire,\n"
    "      and is left for compatibility with older versions.\n"

    subprocess.run([
        "s3fs", bucket_name, mount_point,
        "-o", f"passwd_file={os.path.expanduser('./.passwd-s3fs')}",
        "-o", f"url={endpoint}",
        "-o", "use_path_request_style",
        "-o", f"use_cache={cahce_point}",
        "-o", "ensure_diskfree=2048",   # 20GB剩余空间
        "-o", "stat_cache_interval_expire=86400000" #1000天过期

    ], check=True)






if __name__ == "__main__":

    BUCKET_NAME = "comfyfog-model-r2"
    ACCESS_KEY = "3ca00cd14dec8573caa93bad4508c85e"
    SECRET_KEY = "923d0d14b9a8d50cd5ead34d47ad96e9c5e0eede15044205ca46011c60f0c37a"
    ENDPOINT = "https://191983bb64d1962d6b5fc196ba85de9f.r2.cloudflarestorage.com"
    #ENDPOINT = "https://model.comfyfog.org"

    MOUNT_POINT = "/mnt/cloudflare-r2-test"
    CACHE_POINT = "/tmp/s3fs-cache"

    install_s3fs()
    create_password_file(ACCESS_KEY, SECRET_KEY)
    mount_s3_bucket(BUCKET_NAME, ENDPOINT, MOUNT_POINT, CACHE_POINT)
