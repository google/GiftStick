# Frequently Asked Questions

## Is this an official Google product?

No.

## Does the code support other Cloud hosting services?

Not out of the box.

The uploading code is based on [boto](https://github.com/boto/boto),
and you could create a new class in
[uploader.py](https://github.com/google/GiftStick/blob/master/auto_forensicate/uploader.py)
and implement the private methods to the needs of other Cloud storage services.
Some flags should probably be added to the
[auto_acquire](https://github.com/google/GiftStick/blob/master/auto_forensicate/auto_acquire.py)
main script, and (if you use the image building scripts from the `tools`
directory) add those to `make_bootable_usb_image` function of
[remaster.sh](https://github.com/google/GiftStick/blob/master/tools/remaster.sh)
when the 'double-clickable' helper script is created (search for `EOFORENSICSH`)

## Does this support `newStorage method`? (e.g.: MacOS Fusion Drives)

Probably not.

The script lists block devices that have been detected by the kernel running on
the system (ie: a vanilla Ubuntu).

If the block device doesn't show up when running `lsblk` in the booted OS, it's
not going to be detected.

## What target system does the script support?

If your target system can boot over USB (with EFI) and its devices are
recognized as block devices in a vanilla Xubuntu, then those will be acquired.

Some hardware is still not recognized in the Linux kernel and makes acquisition a
bit more complicated:

* Wifi module used in MacBook post 2016 is still unsupported [see
  bug](https://bugzilla.kernel.org/show_bug.cgi?id=193121). You will need to use
  a USB->RJ45 adapter.

## Does the code work on `$OS`?

This has only been tested on Xubuntu Xenial Xerus (16.04) and Bionic Beaver
(18.04).

## What if the internet connection is not stable?

Then the script will most likely fail. Depending on the failure detected, a
message will be displayed to the user saying they probably should retry by
running the script again.

It performs 'resumable' upload which does handle some errors and will
try to re-send chunks in the vent of some network errors. If internet
connectivity is lost for a significant amount of time, the upload will stop
and you won't be able to resume from the last known uploaded chunk.

## Is this project 'forensically sound'?

Not really.

None of the code used in this project has been certified, and does not follow
and ISO standard.

No write blocking mechanism is currently implemented.

To try and keep some trust about the data being copied from disk, the code also
uploads MD5 and SHA1 hashes for every 128MiB read from the device, as well as
the whole content. This is uploaded alongside the `sdX.image` file, as
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

Yes.

Call the `auto_acquire.py` script with the `--select_disk` flag.

## Why are the ISO remastering script in `tools` so ugly?

These scripts come as helpers to get you started quickly (by setting up GCS and
remastering an vanilla Xubuntu ISO with the acquisition scripts).

The acquisition scripts don't use them.

## Why should I send my data to a remote untrusted Cloud platform?

If this is a risk you're not willing to take, make sure you acquire only
encrypted devices, e.g.: laptops with Full Disk Encryption such as FileVault or
BitLocker.

Alternatively, you can also create your own uploader class to upload data to
a destination of your chosing. (see **Does the code support other Cloud hosting services?**)

You can disable acquiring the firmware of the target system by only enabling the
Disk recipe (see the tool's help).
