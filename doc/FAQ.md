# Frequently Asked Questions

This is a quick page to try and answer some questions raised by the community.

## Is this an official Google product?

No.

## Does the code support other Cloud hosting services?

No.

Though the uploading code is based on the [boto](https://github.com/boto/boto),
and you could create a new class in
[uploader.py](https://github.com/google/GiftStick/blob/master/auto_forensicate/uploader.py)
and implement the private methods to the needs of other Cloud storage services.
Some flags should probably be added to the
[auto_acquire](https://github.com/google/GiftStick/blob/master/auto_forensicate/auto_acquire.py)
main script, and (if you use the image building scripts from the `tools`
directory) add those to `make_bootable_usb_image` function of
[remaster.sh](https://github.com/google/GiftStick/blob/master/tools/remaster.sh)
when the 'double-clickable' helper script is created (search for `EOFORENSICSH`)

## Does this support 'newStorage method' (ie: MacOS Fusion Drives)

Probably not.

The script lists block devices that have been detected by the kernel running on
the system (ie: a vanilla Ubuntu).

If the block device doesn't show up when running `lsblk` in the booted OS, it's
not going to be detected.

## What target system does the script support?

If your target system can boot over USB (with EFI) and its devices are
recognized as block devices in a vanilla Xubuntu, then those will be acquired.

Some hardware is still not recognized in the Linux kernel and make acquisition a
bit more complicated:

* Wifi module used in MacBook post 2016 is still unsupported [see
  bug](https://bugzilla.kernel.org/show_bug.cgi?id=193121). You will need to use
  a USB->RJ45 adapter.

## Does the code work on 'OS'.

This has only been tested on Xubuntu Xenial Xerus (16.04) and Bionic Beaver
(18.04).

## What if the internet connection is not stable?

Then the script will most likely fail. Depending on the failure detected, a
message will be displayed to the user saying they probably should retry by
running the script again.

It performs 'resumable' upload which does handle some error handling and will
try to re-send chunks on some network errors. Though if internet connectivity
is lost for a significant amount of time, the upload will stop, and you won't be
able to resume from the last known uploaded chunk.

## Is this project using 'forensically sound'?

None of the code used in this project has been certified, and does not follow
and ISO standard.

The code is being read off the block device by calling `dcfldd`, which will
then generate MD5 and SHA1 hashes for every 128MiB read from the device, as
well as the whole content. This is uploaded alongside the `sdX.image` file, as
`sdX.hash`.

## Why `dcfldd` and not `acquisition_method_with_compression`?

`dd` clones generate raw images, which can be readily processed by most other
forensics tools.

`dcfldd` was chosen as it's readily available in Ubuntu archives and will
calculate MD5/SHA hashes as it's reading from the block device, even though it
may misbehave when reading faulty drives.

Adding a new recipe, where one can use another tool to read blocks off the
device is [explained here](doc/new_recipe.md)

## Can I also acquire removable disks connected to the target?



## Why are the ISO remastering script in `tools` so ugly?

These scripts come as helpers to get you started quickly (by setting up GCS and
remastering an vanilla Xubuntu ISO with the acquisition scripts).

The acquisition scripts don't use them.
