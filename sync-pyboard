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

  $EXEC [OPTS] BOARD
    -build font file if with font-generator if not already built
    -calculate tzdata CSV with zoneinfo-tool
    -compile src python files except main.py with mpy-cross for board BOARD
    -copy font, python mpy files, main.py, and state-wifi-conf to /pyboard with rshell

  BOARD
    one of:
      pico  | --pico
        use 'mpy-cross-6.2 -march=armv6m'
      pico2 | --pico2
        use 'mpy-cross -march=armv7m'

  OPTS
    -d | --delete
      delete all *.py and *.mpy files on /pyboard before installing
";

sub main(@){
  my $opts = {
    delete => 0,
  };
  my $board = undef;
  while(@_ > 0){
    my $arg = shift;
    if($arg =~ /^(-h|--help)$/){
      print $USAGE;
      exit 0;
    }elsif($arg =~ /^(pico|--pico|armv6m|--armv6m)$/){
      $board = "pico";
    }elsif($arg =~ /^(pico2|--pico2|armv7m|--armv7m)$/){
      $board = "pico2";
    }elsif($arg =~ /^(-d|--delete)$/){
      $$opts{delete} = 1;
    }else{
      die "$USAGE\nERROR: unknown arg $arg\n";
    }
  }

  die "ERROR: missing BOARD (e.g.: pico or pico2)\n" if not defined $board;

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

  if($$opts{delete}){
    run "./rshell", "rm /pyboard/*.mpy; rm /pyboard/*.py";
  }
  my @mpyCrossCmd;
  if($board eq "pico"){
    @mpyCrossCmd = ("mpy-cross-6.2", "-march=armv6m");
  }elsif($board eq "pico2"){
    @mpyCrossCmd = ("mpy-cross", "-march=armv7m");
  }else{
    die "ERROR: unknown board $board\n";
  }

  run "rm", "-rf", "mpy/";
  run "mkdir", "mpy";
  for my $py(glob "src/*.py"){
    my $mpy = $py;
    $mpy =~ s/src\//mpy\//;
    $mpy =~ s/\.py$/.mpy/;
    run (@mpyCrossCmd, $py, "-o", $mpy);
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
