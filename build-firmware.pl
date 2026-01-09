#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(basename dirname);
use Time::HiRes qw(time);

sub ensureMicropythonRepo();
sub installMpyCross($$$);
sub buildFirmware();
sub nowMillis();
sub readProc(@);
sub run(@);

my $EXEC = basename $0;
my $BASE_DIR = dirname $0;

my $PREFIX = "/usr/local";

my $GIT_URL_MICROPYTHON = "https://github.com/teleshoes/micropython";

my $MPY_COMMIT_LATEST = "master";
my $MPY_COMMIT_6_3 = "bdbc869f9ea200c0d28b2bc7bfb60acd9d884e1b";
my $MPY_COMMIT_6_2 = "$MPY_COMMIT_6_3^"; #last commit before version change 6.2=>6.3

my $DIR_FIRMWARE_IMG = "$BASE_DIR/firmware";
my $DIR_MICROPYTHON_REPO = "$BASE_DIR/micropython";

my @GIT_CMD = ("git", "-C", $DIR_MICROPYTHON_REPO);

my $USAGE = "Usage:
  $EXEC -h | --help
    show this message

  $EXEC -m | --mpycross | --mpy-cross | mpy-cross
    -build mpy-cross-6.2 from latest commit before micropython 6.3
      -install to /usr/local/bin/mpy-cross-6.2
    -build mpy-cross from latest micropython
      -install to /usr/local/bin/mpy-cross

  $EXEC -b | uf2 | firmware | build | --uf2 | --firmware | --build
    -build micropython RPI_PICO_W firmware
      from $GIT_URL_MICROPYTHON
    -copy built image to $DIR_FIRMWARE_IMG
    -create/replace symlink $DIR_FIRMWARE_IMG/latest.uf2
";

my $MODE_INSTALL_MPY_CROSS = "install-mpy-cross";
my $MODE_BUILD_FIRMWARE = "build-firmware";

sub main(@) {
  my $mode = undef;
  while(@_ > 0){
    my $arg = shift @_;
    if($arg =~ /^(-h|--help)$/){
      print $USAGE;
      exit 0;
    }elsif($arg =~ /^(-m|((--)?(mpy-cross|mpycross)))$/){
      $mode = $MODE_INSTALL_MPY_CROSS;
    }elsif($arg =~ /^(-b|((--)?(uf2|firmware|build)))$/){
      $mode = $MODE_BUILD_FIRMWARE;
    }else{
      die "$USAGE\nERROR: unknown arg $arg\n";
    }
  }

  if($mode eq $MODE_INSTALL_MPY_CROSS){
    #old GCC necessary for micropython 6.2
    installMpyCross("mpy-cross-6.2", $MPY_COMMIT_6_2, ["-j", 1, "CC=gcc-14"]);
    installMpyCross("mpy-cross", $MPY_COMMIT_LATEST, ["-j", 1]);
  }elsif($mode eq $MODE_BUILD_FIRMWARE){
    buildFirmware();
  }else{
    die "ERROR: missing command\n";
  }
}

sub ensureMicropythonRepo(){
  my @gitCloneCmd = ("git", "clone", $GIT_URL_MICROPYTHON, $DIR_MICROPYTHON_REPO);
  if(not -d $DIR_MICROPYTHON_REPO){
    run @gitCloneCmd;
  }
  die "ERROR: '@gitCloneCmd' failed\n" if not -d $DIR_MICROPYTHON_REPO;

  my $url = readProc @GIT_CMD, "config", "--get", "remote.origin.url";

  if($url ne $GIT_URL_MICROPYTHON){
    die "ERROR: mismatched git urls '$url' vs '$GIT_URL_MICROPYTHON'\n";
  }

  run @GIT_CMD, "checkout", "master";
  run @GIT_CMD, "pull";
  run @GIT_CMD, "submodule", "init";
  run @GIT_CMD, "submodule", "update";
}

sub installMpyCross($$$){
  my ($binaryName, $commit, $makeArgs) = @_;

  ensureMicropythonRepo();

  run @GIT_CMD, "checkout", $commit;

  run "make", "-C", "$DIR_MICROPYTHON_REPO/mpy-cross", "clean";
  if(-d "$DIR_MICROPYTHON_REPO/mpy-cross/build"){
    die "ERROR: mpy-cross build dir exists after make clean\n";
  }

  run "make", "-C", "$DIR_MICROPYTHON_REPO/mpy-cross", @$makeArgs;

  #there is no make install for mpy-cross
  run "sudo", "cp", "$DIR_MICROPYTHON_REPO/mpy-cross/build/mpy-cross", "$PREFIX/bin/$binaryName";

  if(not -f "$DIR_MICROPYTHON_REPO/mpy-cross/build/mpy-cross"){
    die "ERROR: mpy-cross compilation failed\n";
  }
}

sub buildFirmware(){
  ensureMicropythonRepo();

  my $picoFW = "$DIR_MICROPYTHON_REPO/firmware_RPI_PICO_W.uf2";
  my $pico2FW = "$DIR_MICROPYTHON_REPO/firmware_RPI_PICO2_W.uf2";

  my $latestPicoFW = "$DIR_FIRMWARE_IMG/latest_pico.uf2";
  my $latestPico2FW = "$DIR_FIRMWARE_IMG/latest_pico2.uf2";

  run "rm", "-f", $picoFW, $pico2FW, $latestPicoFW, $latestPico2FW;

  run "cd '$DIR_MICROPYTHON_REPO' && ./build-pico-w.sh";

  die "ERROR: firmware build failed\n" if not -f $picoFW or not -f $pico2FW;

  if(not -d "$DIR_FIRMWARE_IMG/"){
    run "mkdir", "-p", $DIR_FIRMWARE_IMG;
    if(not -d "$DIR_FIRMWARE_IMG/"){
      die "ERROR: $DIR_FIRMWARE_IMG/ is not a dir\n" if not -d "$DIR_FIRMWARE_IMG/";
    }
  }

  my $gitCommit = readProc @GIT_CMD, "show", "-s", "--format=%h";
  my $gitEpoch = readProc @GIT_CMD, "show", "-s", "--format=%at";
  my $gitDtm = readProc "date", "--date=\@$gitEpoch", "+%Y-%m-%d_%H%M%S";
  my $nowMillis = nowMillis();

  my $fileNamePicoDestFW = "picolcd_firmware_RPI_PICO_W_${gitDtm}_${gitCommit}_${nowMillis}.uf2";
  my $fileNamePico2DestFW = "picolcd_firmware_RPI_PICO2_W_${gitDtm}_${gitCommit}_${nowMillis}.uf2";

  run "cp", $picoFW, "$DIR_FIRMWARE_IMG/$fileNamePicoDestFW";
  run "cp", $pico2FW, "$DIR_FIRMWARE_IMG/$fileNamePico2DestFW";

  run "ln", "-s", $fileNamePicoDestFW, $latestPicoFW;
  run "ln", "-s", $fileNamePico2DestFW, $latestPico2FW;
}

sub nowMillis(){
  return int(time() * 1000.0 + 0.5);
}

sub readProc(@){
  open my $cmdH, "-|", @_ or die "ERROR: could not run '@_'\n$!\n";
  my $out = join '', <$cmdH>;
  close $cmdH;

  chomp $out;
  return $out;
}

sub run(@){
  print "@_\n";
  system @_;
  if($? != 0){
    die "ERROR: '@_' failed\n$!\n";
  }
}

&main(@ARGV);
