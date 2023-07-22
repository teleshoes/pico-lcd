#!/usr/bin/perl
use strict;
use warnings;

my @files = qw(
  font5x8.bin
  wifi-conf.txt
  src/main.py
  mpy/font-generator.mpy
  mpy/lcdFont.mpy
  mpy/lcd.mpy
);

sub main(@){
  if(not -f "font5x8.bin"){
    system "python", "src/font-generator.py";
  }
  if(not -f "font5x8.bin"){
    die "ERROR: could not generate font binary\n";
  }

  system "rm", "-rf", "mpy/";
  system "mkdir", "mpy";
  for my $py(glob "src/*.py"){
    my $mpy = $py;
    $mpy =~ s/src\//mpy\//;
    $mpy =~ s/\.py$/.mpy/;
    system "mpy-cross", "-march=armv6m", $py, "-o", $mpy;
  }

  for my $file(@files){
    if(not -e $file){
      die "ERROR: missing file $file\n";
    }
  }
  system "./rshell", "cp", @files, "/pyboard";
}

&main(@ARGV);
