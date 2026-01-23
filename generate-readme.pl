#!/usr/bin/perl
use strict;
use warnings;
use File::Basename qw(basename);

sub getMarkupSyntax();

my $EXEC = basename $0;

my $USAGE = "Usage:
  $EXEC -h|--help
    show this message

  $EXEC
    edit README.md by parsing src/doc.py and src/lcdFont.py
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

  my $readme = `cat README.md`;

  my $cmdDoc = `python src/doc.py`;
  $cmdDoc =~ s/^\n+//;
  $cmdDoc =~ s/\n+$//;

  my $markupSyntax = getMarkupSyntax();
  $markupSyntax =~ s/^\n+//;
  $markupSyntax =~ s/\n+$//;

  $readme =~ s/
    <!--\s*COMMAND_DOC\s*-->
    .*
    <!--\s*COMMAND_DOC\s*-->
  /<!-- COMMAND_DOC -->\n$cmdDoc\n<!-- COMMAND_DOC -->/sxi;

  $readme =~ s/
    <!--\s*MARKUP_SYNTAX\s*-->
    .*
    <!--\s*MARKUP_SYNTAX\s*-->
  /<!-- MARKUP_SYNTAX -->\n$markupSyntax\n<!-- MARKUP_SYNTAX -->/sxi;

  open my $fh, "> README.md" or die "ERROR: could not write README.md\n$!\n";
  print $fh $readme;
  close $fh;
}

sub getMarkupSyntax(){
  my $lcdFont = `cat src/lcdFont.py`;
  if($lcdFont !~ /###\s*MARKUP_SYNTAX\s*###(.*)###\s*MARKUP_SYNTAX\s*###/s){
    die "ERROR: could not parse markup syntax in lcdFont\n";
  }
  my $lcdFontMarkupSyntax = $1;
  $lcdFontMarkupSyntax =~ s/^[ \t\r\n]+//;
  $lcdFontMarkupSyntax =~ s/[ \t\r\n]+$//;
  my $fmt = "";
  my @lines = split /\n/, $lcdFontMarkupSyntax;
  for my $line(@lines){
    $line =~ s/^\s*#//;
    $fmt .= "$line\n";
  }
  return $fmt;
}

&main(@ARGV);
