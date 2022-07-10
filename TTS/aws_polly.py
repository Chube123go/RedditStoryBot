#!/usr/bin/env python3
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError

import sys
from utils import settings
from attr import attrs

from TTS.common import get_random_voice


voices = [
    'Brian',
    'Emma',
    'Russell',
    'Joey',
    'Matthew',
    'Joanna',
    'Kimberly',
    'Amy',
    'Geraint',
    'Nicole',
    'Justin',
    'Ivy',
    'Kendra',
    'Salli',
    'Raveena',
]


@attrs(auto_attribs=True)
class AWSPolly:
    random_voice: bool = False
    max_chars: int = 0

    async def run(
            self,
            text,
            filepath,
    ):
        session = Session(profile_name='polly')
        polly = session.client("polly")
        voice = (
            get_random_voice(voices)
            if self.random_voice
            else str(settings.config['settings']['tts']['aws_polly_voice']).capitalize()
            if str(settings.config['settings']['tts']['aws_polly_voice']).lower() in [voice.lower() for voice in voices]
            else get_random_voice(voices)
        )
        try:
            # Request speech synthesis
            response = polly.synthesize_speech(
                Text=text, OutputFormat="mp3", VoiceId=voice, Engine="neural"
            )
        except (BotoCoreError, ClientError) as error:
            # The service returned an error, exit gracefully
            print(error)
            sys.exit(-1)

        # Access the audio stream from the response
        if 'AudioStream' in response:
            file = open(filepath, "wb")
            file.write(response["AudioStream"].read())
            file.close()
            # print_substep(f"Saved Text {idx} to MP3 files successfully.", style="bold green")

        else:
            # The response didn't contain audio data, exit gracefully
            print('Could not stream audio')
            sys.exit(-1)
