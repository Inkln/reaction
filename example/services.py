import asyncio
import json
import logging
import os
from typing import List, Any

import cv2
import torch
from albumentations import Compose, Normalize, LongestMaxSize, PadIfNeeded
from albumentations.torch import ToTensor

from common import rpc_uri
from reaction.rpc import RabbitRPC as RPC


@RPC(rpc_uri)
def recognize(*imgs) -> List[Any]:
    return [i.shape for i in imgs]


@RPC(rpc_uri)
def recognize_passport(*imgs) -> List[Any]:
    return [i.shape[0] / i.shape[1] for i in imgs]


@RPC(rpc_uri, timeout=3)
async def square(*values) -> List[float]:
    await asyncio.sleep(1)
    return [v ** 2 for v in values]


class SimpleModel:
    def __init__(self):
        self.model = None
        self.class2tag = None
        self.tag2class = None

    def load(self, path='/model'):
        self.model = torch.jit.load(os.path.join(path, 'model.pth'))
        with open(os.path.join(path, 'tag2class.json')) as fin:
            self.tag2class = json.load(fin)
            self.class2tag = {v: k for k, v in self.tag2class.items()}
            logging.debug(f'class2tag: {self.class2tag}')

    @RPC(rpc_uri, name='simple_model', pool_size=1, batch_size=4)
    def predict(self, *imgs) -> List[str]:
        logging.debug(f'batch size: {len(imgs)}')
        transofrm = Compose([
            LongestMaxSize(max_size=224),
            PadIfNeeded(224, 224, border_mode=cv2.BORDER_CONSTANT),
            Normalize(),
            ToTensor(),
        ])

        input_ts = [transofrm(image=img)["image"] for img in imgs]
        logging.debug(f'input_ts: {input_ts}')
        input_t = torch.stack(input_ts)
        logging.debug(f'input_t: {input_t.shape}')
        output_ts = self.model(input_t)
        logging.debug(f'output_ts: {output_ts.shape}')

        res = []
        for output_t in output_ts:
            tag = self.class2tag[output_t.argmax().item()]
            logging.debug(f'result: {tag}')
            res.append(tag)
        return res


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(square.consume())
    loop.create_task(recognize.consume())
    loop.create_task(recognize_passport.consume())

    m = SimpleModel()
    m.load()
    loop.create_task(m.predict.consume())

    loop.run_forever()