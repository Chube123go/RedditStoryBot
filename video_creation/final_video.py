#!/usr/bin/env python3
import multiprocessing
import os
import re
from os.path import exists
from typing import Tuple, Any

import translators as ts

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    concatenate_videoclips,
    concatenate_audioclips,
    CompositeVideoClip,
)
from moviepy.video.io.ffmpeg_tools import ffmpeg_merge_video_audio, ffmpeg_extract_subclip
from rich.console import Console
from rich.progress import track

from utils.cleanup import cleanup
from utils.console import print_step, print_substep
from utils.videos import save_data
from utils import settings
from video_creation.background import download_background, chop_background_video

console = Console()

W, H = 1080, 1920  # TODO move to config

max_length: int = 50  # TODO move to config
time_before_first_picture: float = 1  # TODO move to config
time_before_tts: float = 0.5  # TODO move to config
time_between_pictures: float = 1  # TODO move to config
delay_before_end: int = 1


def name_normalize(
        name: str
) -> str:
    name = re.sub(r'[?\\"%*:|<>]', "", name)
    name = re.sub(r'( [w,W]\s?\/\s?[o,O,0])', r' without', name)
    name = re.sub(r'( [w,W]\s?\/)', r' with', name)
    name = re.sub(r'(\d+)\s?\/\s?(\d+)', r'\1 of \2', name)
    name = re.sub(r'(\w+)\s?\/\s?(\w+)', r'\1 or \2', name)
    name = re.sub(r'\/', '', name)

    lang = settings.config['reddit']['thread']['post_lang']
    if lang:
        print_substep('Translating filename...')
        translated_name = ts.google(name, to_language=lang)
        return translated_name

    else:
        return name


def make_final_video(
        indexes_of_clips: list,
        reddit_obj: dict,
        background_config: Tuple[str, str, str, Any],
) -> None:
    """
    Gathers audio clips, gathers all screenshots, stitches them together and saves the final video to assets/temp

    Args:
        indexes_of_clips (list): Indexes of voiced comments
        reddit_obj (dict): The reddit object that contains the posts to read.
        background_config (Tuple[str, str, str, Any]): The background config to use.
    """
    print_step('Creating the final video 🎥')
    VideoFileClip.reW = lambda clip: clip.resize(width=W)
    VideoFileClip.reH = lambda clip: clip.resize(width=H)
    opacity = settings.config['settings']['opacity']

    def create_audio_clip(
            clip_title: str | int,
            clip_start: float,
    ) -> 'AudioFileClip':
        return (
            AudioFileClip(f'assets/temp/mp3/{clip_title}.mp3')
            .set_start(clip_start)
        )

    video_duration = 0

    # Gather all audio clips
    audio_clips = list()
    correct_audio_offset = time_before_tts * 2 + time_between_pictures

    audio_title = create_audio_clip(
        'title',
        time_before_first_picture + time_before_tts,
    )
    video_duration += audio_title.duration + time_before_first_picture + time_before_tts
    audio_clips.append(audio_title)
    indexes_for_videos = list()

    for idx, audio in track(
            enumerate(indexes_of_clips, start=1),
            description='Gathering audio clips...',
    ):
        temp_audio_clip = create_audio_clip(
            audio,
            correct_audio_offset + video_duration,
        )
        if video_duration + temp_audio_clip.duration + correct_audio_offset + delay_before_end <= max_length:
            video_duration += temp_audio_clip.duration + correct_audio_offset
            audio_clips.append(temp_audio_clip)
            indexes_for_videos.append(idx)

    video_duration += delay_before_end

    audio_composite = concatenate_audioclips(audio_clips)

    console.log('[bold green] Video Will Be: %.2f Seconds Long' % video_duration)
    # Gather all images
    new_opacity = 1 if opacity is None or float(opacity) >= 1 else float(opacity)  # TODO move to pydentic and percents

    def create_image_clip(
            image_title: str | int,
            audio_start: float,
            audio_end: float,
            audio_duration: float,
    ) -> 'ImageClip':
        return (
            ImageClip(f'assets/temp/png/{image_title}.png')
            .set_start(audio_start - time_before_tts)
            .set_end(audio_end + time_before_tts)
            .set_duration(time_before_tts * 2 + audio_duration, change_end=False)
            .set_opacity(new_opacity)
            .resize(width=W - 100)
        )

    # add title to video
    image_clips = list()

    image_clips.append(
        create_image_clip(
            'title',
            audio_clips[0].start,
            audio_clips[0].end,
            audio_clips[0].duration
        )
    )

    for photo_idx in indexes_for_videos:
        image_clips.append(
            create_image_clip(
                f'comment_{indexes_of_clips[photo_idx]}',
                audio_clips[photo_idx].start,
                audio_clips[photo_idx].end,
                audio_clips[photo_idx].duration
            )
        )

    # if os.path.exists("assets/mp3/posttext.mp3"):
    #    image_clips.insert(
    #        0,
    #        ImageClip("assets/png/title.png")
    #        .set_duration(audio_clips[0].duration + audio_clips[1].duration)
    #        .set_position("center")
    #        .resize(width=W - 100)
    #        .set_opacity(float(opacity)),
    #    )
    # else: story mode stuff
    img_clip_pos = background_config[3]
    image_concat = concatenate_videoclips(image_clips).set_position(img_clip_pos)
    image_concat.audio = audio_composite

    download_background(background_config)
    chop_background_video(background_config, video_duration)
    background_clip = (
        VideoFileClip('assets/temp/background.mp4')
        .set_start(0)
        .set_end(video_duration + delay_before_end)
        .without_audio()
        .resize(height=H)
    )

    back_video_width, back_video_height = background_clip.size

    # Fix for crop with vertical videos
    if back_video_width < H:
        background_clip = (
            background_clip
            .resize(width=W)
        )
        back_video_width, back_video_height = background_clip.size
        background_clip = background_clip.crop(
            x1=0,
            x2=back_video_width,
            y1=back_video_height / 2 - H / 2,
            y2=back_video_height / 2 + H / 2
        )
    else:
        background_clip = background_clip.crop(
            x1=back_video_width / 2 - W / 2,
            x2=back_video_width / 2 + W / 2,
            y1=0,
            y2=back_video_height
        )

    final = CompositeVideoClip([background_clip, image_concat])
    title = re.sub(r'[^\w\s-]', '', reddit_obj['thread_title'])
    idx = re.sub(r'[^\w\s-]', '', reddit_obj['thread_id'])

    filename = f'{name_normalize(title)}.mp4'
    subreddit = settings.config['reddit']['thread']['subreddit']

    save_data(subreddit, filename, title, idx, background_config[2])

    if not exists(f'./results/{subreddit}'):
        print_substep('The results folder didn\'t exist so I made it')
        os.makedirs(f'./results/{subreddit}')

    final.write_videofile(
        'assets/temp/temp.mp4',
        fps=30,
        audio_codec='aac',
        audio_bitrate='192k',
        verbose=False,
        threads=multiprocessing.cpu_count(),
    )
    if settings.config['settings']['background_audio']:
        print('[bold green] Merging background audio with video')
        if not exists('assets/backgrounds/background.mp3'):
            print_substep(
                'Cannot find assets/backgrounds/background.mp3 audio file didn\'t so skipping.'
            )
            ffmpeg_extract_subclip(
                'assets/temp/temp.mp4',
                0,
                video_duration,
                targetname=f'results/{subreddit}/{filename}',
            )
        else:
            ffmpeg_merge_video_audio(
                'assets/temp/temp.mp4',
                'assets/backgrounds/background.mp3',
                'assets/temp/temp_audio.mp4',
            )
            ffmpeg_extract_subclip(  # check if this gets run
                'assets/temp/temp_audio.mp4',
                0,
                video_duration,
                targetname=f'results/{subreddit}/{filename}',
            )
    else:
        print('debug duck')
        ffmpeg_extract_subclip(
            'assets/temp/temp.mp4',
            0,
            video_duration,
            targetname=f'results/{subreddit}/{filename}',
        )
    print_step('Removing temporary files 🗑')
    cleanups = cleanup()
    print_substep(f'Removed {cleanups} temporary files 🗑')
    print_substep('See result in the results folder!')

    print_step(
        f'Reddit title: {reddit_obj["thread_title"]} \n Background Credit: {background_config[2]}'
    )
