#!/usr/bin/perl
use strict;
use warnings;

my @files = qw(
  font5x8.bin
  wifi-conf.txt
  src/font-generator.py
  src/lcdFont.py
  src/lcd.py
  src/main.py
  src/rgb332_to_rgb565.py
);

sub main(@){
  if(not -f "font5x8.bin"){
    system "python", "src/font-generator.py";
  }
  if(not -f "font5x8.bin"){
    die "ERROR: could not generate font binary\n";
  }
  for my $file(@files){
    if(not -e $file){
      die "ERROR: missing file $file\n";
    }
  }
  system "./rshell", "cp", @files, "/pyboard";
}

&main(@ARGV);
