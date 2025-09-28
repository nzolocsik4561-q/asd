#!/usr/bin/env ruby
# frozen_string_literal: true

def summarize(text)
  counts = Hash.new(0)
  text.split.each { |word| counts[word.downcase] += 1 }
  counts.sort_by { |word, count| [-count, word] }
end

if $PROGRAM_NAME == __FILE__
  sample = "Codex codex demo script"
  summarize(sample).each do |word, count|
    puts format("%s => %d", word, count)
  end
end
