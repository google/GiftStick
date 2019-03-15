# GiftStick

![](doc/gift_video.gif)

## Summary

This project contains code which allows an inexperimented user to easily (one
click) upload forensics evidence (such as some information about the system,
a full disk image as well as the system's firmware, if supported) from a
target device (that will boot on an external device containing the code)
to Google Cloud Storage.

It supports configuring what artifacts to collect and which Cloud credentials
to use.

This is not an officially supported Google product.

## Usage

### Make a bootable disk image with the provided script

In the `tools` directory, the script `remaster.sh` help you with the process of:
* Creating a bootable USB disk image with the required dependencies
* Make sure the image will boot on EFI enabled systems, as well as install
[third-party input drivers for latest
MacBook](https://github.com/cb22/macbook12-spi-driver)
* Create a GCS bucket to receive the evidence, as well as a Service Account
with the proper roles & ACL.
* Make an icon on the system's Desktop with a clickable icon to start the
acquisition process.

It needs as input :
* a vanilla Ubuntu ISO (tested with XUbuntu 18.04)
* the name of your GCP project
* the name of the GCS bucket (remember those need to be globally unique)

You need to have installed the [Google Cloud SDK](https://cloud.google.com/sdk/install)
and have [SetUp the environment and logged
in](https://cloud.google.com/sdk/docs/initializing). Then run:

```
bash tools/remaster.sh \
  --project some-forensics-project-XYZ \
  --bucket giftstick-uploads-XYZ
  --source_iso gift_stick/xubuntu-18.04-desktop-amd64.iso
```


### Manually set up the required Google Cloud environment & call the script

First, the script needs credentials (for example, of a Service Account) that
provide the following roles (see [IAM
roles](https://cloud.google.com/storage/docs/access-control/iam-roles)):
* `roles/storage.objectCreator`, to be able to create (but not overwrite) new
storage objects,
* (optional) `roles/logging.logWriter` for the StackDriver logging system.

These credentials needs to be downloaded and saved as a JSON file. For
example, using a Service Account named
`uploader@giftstick-project.iam.gserviceaccount.com`, you can create a new key
and save it as `credentials.json`:

```
gcloud iam service-accounts --project giftstick-project keys create \
        --iam-account "uploader@giftstick-project.iam.gserviceaccount.com" \
        credentials.json
```

You can now then include the `auto_forensicate` folder, as well as the
`credentials.json` file on a bootable USB of your choice, where the dependencies
have been installed (see below).

Once you have booted the system to acquire evidence from that newly created
USB stick, and upload it to a GCS url
`gs://giftstick-bucket/forensics_evidence/` you can run the acquisition script
this way:

```
cd auto_forensicate
sudo python auto_forensicate.py \
    --gs_keyfile=credentials.json \
    --logging stdout \
    --acquire all \
    gs://giftstick-bucket/forensics_evidence/
```

You'll then get the following hierarchy in your GCS bucket:

```
gs://giftstick-bucket/forensics_evidence/20181104-1543/SYSTEM_SERIAL/system_info.txt
gs://giftstick-bucket/forensics_evidence/20181104-1543/SYSTEM_SERIAL/stamp.json
gs://giftstick-bucket/forensics_evidence/20181104-1543/SYSTEM_SERIAL/Disks/
gs://giftstick-bucket/forensics_evidence/20181104-1543/SYSTEM_SERIAL/Disks/sda.hash
gs://giftstick-bucket/forensics_evidence/20181104-1543/SYSTEM_SERIAL/Disks/sda.image
```

## Dependencies

The script has been tested on the Xenial (16.04) and Bionic Beaver (18.04)
versions of Xubuntu.

The following packages should be installed in the system you're booting into:

* `sudo apt install dcfldd python-pip zenity`
* For Chipsec (optional)
`apt install python-dev libffi-dev build-essential gcc nasm`


## Acquired evidence

Currently the script uploads the following data:

* System information (output of `dmidecode`)
* For each block device that is most likely an internal disk:
  * all the bytes
  * hashes
  * the device's information (output of udevadm)
* The system's firmware, dumped with
  [Chipsec](https://github.com/chipsec/chipsec)


## FAQ

Some answers to Frequenly Asked Questions can be [found here](doc/FAQ.md)
