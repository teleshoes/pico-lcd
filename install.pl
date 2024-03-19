#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(dirname);
use Time::HiRes qw(time);

sub nowMillis();

my @files = qw(
  font5x8.bin
  wifi-conf.txt
  src/main.py
  mpy/app.mpy
  mpy/doc.mpy
  mpy/lcdFont.mpy
  mpy/lcd.mpy
  mpy/rtc.mpy
);

#DS3231 rtc can only handle 2 centuries anyway
my $TZ_START_YEAR = 1900;
my $TZ_END_YEAR = 2100;

my @TZ_ZONENAMES = qw(
  America/New_York
);

sub main(@){
  if(not -f "font5x8.bin"){
    system "python", "src/font-generator.py";
  }
  if(not -f "font5x8.bin"){
    die "ERROR: could not generate font binary\n";
  }

  my $pyboardTmpDir = "pyboard-tmp-" . nowMillis();
  system "mkdir", $pyboardTmpDir;

  #calculate+install tzdata CSV files
  system "./zoneinfo-tool",
    "-c", "$TZ_START_YEAR,$TZ_END_YEAR",
    "--skip-existing",
    @TZ_ZONENAMES,
  ;
  system "cp", "-ar", "zoneinfo/", "$pyboardTmpDir/";


  system "rm", "-rf", "mpy/";
  system "mkdir", "mpy";
  for my $py(glob "src/*.py"){
    my $mpy = $py;
    $mpy =~ s/src\//mpy\//;
    $mpy =~ s/\.py$/.mpy/;
    system "mpy-cross", "-march=armv6m", $py, "-o", $mpy;
    system "touch", $mpy, "-r", $py;
  }

  system "cp", "-ar", @files, "$pyboardTmpDir/";

  system "./rshell", "rsync", "$pyboardTmpDir/", "/pyboard/";

  system "rm", "-rf", "$pyboardTmpDir/";
}

sub nowMillis(){
  return int(time() * 1000.0 + 0.5);
}

&main(@ARGV);
