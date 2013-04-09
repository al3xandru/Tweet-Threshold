> "The most essential service of the next decade will be the one that keeps you the best informed in the least amount of time. Theres more to life than staring at screens all day."

\- [Mike Davidson, VP of design, Twitter, and founder, Newsvine](http://alistapart.com/article/what-we-learned-in-2012)

The line between content producers and advertisers grows thin. All content creators demand your attention, whether they be J.J. Abrams and his Star Wars movie or your high school friend from 30 years ago and her Facebook post about her dog's anxiety problem. As content becomes easier to produce and distribute, we need better tools to help us filter what we want from the sea of noise trying to get at us. This [Tweet Threshold Python script posted to Github](https://github.com/mshea/Tweet-Threshold) is an experiment in automatically filtering tweets pulled from a list of Twitter accounts based on a Threshold.

You can [download the script](https://github.com/mshea/Tweet-Threshold) and run it yourself anywhere you can run Python. I've released it under a [Creative Commons Attribution-NonCommercial-ShareAlike 3.0 license](http://creativecommons.org/licenses/by-nc-sa/3.0/) so you can distribute it, modify it, and share it as long as you release it under a similar license and attribute the original program to me.

## What This Script Does

This script reaches out to Twitter and pulls down the latest 100 tweets in JSON from one or more authenticated timelines. It saves any tweets containing a URL to a local SQLite3 database. From this database, the script outputs am HTML page filtered by an algorithm based on retweets / followers with a minimum threshold so you just get the ones a lot of people thought were retweet-worthy. Here is an example in my [Tweet News page](http://mikeshea.net/news/).

## How to Use This Script

You'll want some experience working with Python to run this script. This script uses [Tweepy](https://github.com/tweepy/tweepy) to handle the interactions with Twitter and [Jinja2](http://jinja.pocoo.org/docs/) to handle the HTML templating.

To run this script, you'll need to register this script as an application with Twitter. See [https://dev.twitter.com/apps](https://dev.twitter.com/apps) for more information.

Change the parameters in "fetch_tweets.py" script to your own twitter authentication codes and the local directories where you want the results. Modify the html_template.txt template to suit your needs. Set up a scheduled event like a cronjob to run "fetch_tweets.py" once every hour.

The index.html file only shows tweets from yesterday and the previous seven days. This is on purpose. Who really needs up-t-the-minute news these days? Relax and spend some time in a park for God's sake.

## A Small Solution to a Growing Problem

We're going to need better agents like this if we want to take back our attention from the hordes of content producers demanding their space in our brains. I'm hoping to continue working on this problem or finding better solutions. We can't trust the big companies like Twitter or Google to do this for us. It isn't in their interests to help us avoid using their sites. We can only trust our own tools and our ourselves to do it for us.

If you're interested in this topic, know of some other tools like this, or have used the script and found it useful, please send me an email to mike@mikeshea.net to let me know.