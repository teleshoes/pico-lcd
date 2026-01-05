#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(basename dirname);
use Time::HiRes qw(time);

sub nowMillis();
sub run(@);

my @FILES = qw(
  font5x8.bin
  state-wifi-conf
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

my $EXEC = basename $0;

my $USAGE = "Usage:
  $EXEC -h | --help
    show this message

  $EXEC ARCH
    -build font file if with font-generator if not already built
    -calculate tzdata CSV with zoneinfo-tool
    -compile src python files except main.py with mpy-cross for architecture ARCH
    -copy font, python mpy files, main.py, and state-wifi-conf to /pyboard with rshell

  ARCH
    one of:
      pico  | --pico  | armv6m | --armv6m
        use --march=armv6m for mpy-cross
      pico2 | --pico2 | armv7m | --armv7m
        use --march=armv7m for mpy-cross
";

sub main(@){
  my $arch = undef;
  while(@_ > 0){
    my $arg = shift;
    if($arg =~ /^(-h|--help)$/){
      print $USAGE;
      exit 0;
    }elsif($arg =~ /^(pico|--pico|armv6m|--armv6m)$/){
      $arch = "armv6m";
    }elsif($arg =~ /^(pico2|--pico2|armv7m|--armv7m)$/){
      $arch = "armv7m";
    }else{
      die "$USAGE\nERROR: unknown arg $arg\n";
    }
  }

  die "ERROR: missing ARCH (e.g.: pico or pico2)\n" if not defined $arch;

  run "pkill -9 rshell";
  if(not -f "font5x8.bin"){
    run "python", "src/font-generator.py";
  }
  if(not -f "font5x8.bin"){
    die "ERROR: could not generate font binary\n";
  }

  my $pyboardTmpDir = "pyboard-tmp-" . nowMillis();
  run "mkdir", $pyboardTmpDir;

  #calculate+install tzdata CSV files
  run "./zoneinfo-tool",
    "-c", "$TZ_START_YEAR,$TZ_END_YEAR",
    "--skip-existing",
    @TZ_ZONENAMES,
  ;
  run "cp", "-ar", "zoneinfo/", "$pyboardTmpDir/";


  run "rm", "-rf", "mpy/";
  run "mkdir", "mpy";
  for my $py(glob "src/*.py"){
    my $mpy = $py;
    $mpy =~ s/src\//mpy\//;
    $mpy =~ s/\.py$/.mpy/;
    run "mpy-cross", "-march=$arch", $py, "-o", $mpy;
    run "touch", $mpy, "-r", $py;
  }

  run "cp", "-ar", @FILES, "$pyboardTmpDir/";

  run "./rshell", "rsync", "$pyboardTmpDir/", "/pyboard/";

  run "rm", "-rf", "$pyboardTmpDir/";
}

sub nowMillis(){
  return int(time() * 1000.0 + 0.5);
}

sub run(@){
  print "@_\n";
  system @_;
}

&main(@ARGV);
