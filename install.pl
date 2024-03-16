#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(dirname);

my @files = qw(
  font5x8.bin
  wifi-conf.txt
  src/main.py
  mpy/font-generator.mpy
  mpy/lcdFont.mpy
  mpy/lcd.mpy
);

#DS3231 rtc can only handle 2 centuries anyway
my $TZ_START_YEAR = 1900;
my $TZ_END_YEAR = 2100;

my @TZ_ZONENAMES = qw(
);

sub main(@){
  if(not -f "font5x8.bin"){
    system "python", "src/font-generator.py";
  }
  if(not -f "font5x8.bin"){
    die "ERROR: could not generate font binary\n";
  }

  #calculate+install tzdata CSV files
  system "./zoneinfo-tool",
    "-c", "$TZ_START_YEAR,$TZ_END_YEAR",
    "--skip-existing",
    @TZ_ZONENAMES,
  ;
  system "./rshell", "rsync", "--mirror", "./zoneinfo", "/pyboard/zoneinfo/";


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
