#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(basename dirname);

sub installFirmware($$$);
sub run(@);
sub tryrun(@);

my $EXEC = basename $0;

my $DIR_MNT = "/media";
my $DIR_FIRMWARE = dirname($0) . "/firmware";

my $PICO1_LABEL = "RPI-RP2";
my $PICO2_LABEL = "RP2350";

my $USAGE = "Usage:
  $EXEC -h|--help
    show this message

  $EXEC
    -detect any pico/pico2 block devices with `blkid`
    -select the first such block device
    -mount the block device
    -copy the latest pico or pico2 firmware
    -run sync

    similar to:
       ######
       #PICO
       DEV=`blkid -L $PICO1_LABEL`
       mkdir $DIR_MNT/$PICO1_LABEL
       mount \$DEV $DIR_MNT/$PICO1_LABEL
       cp -L firmware/latest_pico.uf2  $DIR_MNT/$PICO1_LABEL
       sync
       ######
       #PICO2
       DEV=`blkid -L $PICO2_LABEL`
       mkdir $DIR_MNT/$PICO2_LABEL
       mount \$DEV $DIR_MNT/$PICO2_LABEL
       cp -L firmware/latest_pico2.uf2 $DIR_MNT/$PICO2_LABEL
       sync
       #####
";

sub main(@){
  while(@_ > 0){
    my $arg = shift;
    if($arg =~ /^(-h|--help)$/){
      print $USAGE;
      exit 0;
    }else{
      die "ERROR: unknown arg $arg\n";
    }
  }

  my $pico1Dev = `sudo blkid -L $PICO1_LABEL`;
  chomp $pico1Dev;
  my $pico2Dev = `sudo blkid -L $PICO2_LABEL`;
  chomp $pico2Dev;

  if(-b $pico1Dev){
    installFirmware($PICO1_LABEL, $pico1Dev, "$DIR_FIRMWARE/latest_pico.uf2");
  }elsif(-b $pico2Dev){
    installFirmware($PICO2_LABEL, $pico2Dev, "$DIR_FIRMWARE/latest_pico2.uf2");
  }else{
    die "ERROR: no block device found for label $PICO1_LABEL or $PICO2_LABEL\n";
  }
}

sub installFirmware($$$){
  my ($label, $dev, $fw) = @_;
  if(not -f $fw){
    die "ERROR: missing firmware $fw\n";
  }

  my $mntDir = "$DIR_MNT/$label";
  if(-d $mntDir){
    tryrun "sudo", "umount", "-l", $mntDir;
    tryrun "sudo", "rmdir", $mntDir;
  }
  if(-d $mntDir){
    die "ERROR: could not remove $mntDir\n";
  }

  run "sudo", "mkdir", "-p", $mntDir;
  run "sudo", "mount", $dev, $mntDir;

  run "sudo", "cp", "-L", $fw, "$mntDir/";
  run "sync";

  tryrun "sudo", "umount", "-l", $mntDir;
  tryrun "sudo", "rmdir", $mntDir;

  print "done\n";
}

sub run(@){
  tryrun(@_);
  if($? != 0){
    die "ERROR: @_ failed\n$!\n";
  }
}
sub tryrun(@){
  print "@_\n";
  system @_;
}

&main(@ARGV);
