from contextlib import contextmanager
from tarfile import TarFile
from zipfile import ZipFile
from pathlib import Path, PurePath
from fnmatch import fnmatch

import attr


NEW_PATH = Path('.dephell') / 'archives'


EXTRACTORS = {
    '.zip': ZipFile,
    '.whl': ZipFile,
    '.tar': TarFile.taropen,
    '.tar.gz': TarFile.gzopen,
    '.tar.bz2': TarFile.bz2open,
    '.tar.xz': TarFile.xzopen,
}


@attr.s()
class ArchiveStream:
    descriptor = attr.ib()
    cache_path = attr.ib()
    member_path = attr.ib()
    mode = attr.ib()

    def read(self):
        path = self.cache_path / self.member_path
        if path.exists():
            raise FileExistsError('file created between open and read')

        # extract to cache
        member = self.descriptor.getmember(str(self.member_path))
        self.descriptor.extract(member=member, path=str(self.cache_path))

        # read from cache
        with path.open(self.mode) as stream:
            return stream.read()


@attr.s()
class ArchivePath:
    archive_path = attr.ib()
    cache_path = attr.ib()
    member_path = attr.ib(factory=PurePath)
    _descriptor = attr.ib(default=None, repr=False)

    @property
    def extractor(self):
        extension = ''.join(self.archive_path.suffixes)
        return EXTRACTORS[extension]

    @contextmanager
    def get_descriptor(self):
        if self._descriptor is not None:
            yield self._descriptor
        else:
            with self.extractor(str(self.archive_path)) as descriptor:
                self._descriptor = descriptor
                try:
                    yield self._descriptor
                except Exception:
                    self._descriptor = None
                    raise

    @contextmanager
    def open(self, mode='r'):
        # read from cache
        path = self.cache_path / self.member_path
        if path.exists():
            with path.open() as stream:
                yield stream
        else:
            with self.get_descriptor() as descriptor:
                yield ArchiveStream(
                    descriptor=descriptor,
                    cache_path=self.cache_path,
                    member_path=self.member_path,
                    mode=mode,
                )

    def glob(self, pattern):
        with self.get_descriptor() as descriptor:
            for member in descriptor.getmembers():
                if fnmatch(name=member.name, pat=pattern):
                    obj = self.__class__(
                        archive_path=self.archive_path,
                        cache_path=self.cache_path,
                        member_path=PurePath(member.name),
                    )
                    obj._descriptor = self._descriptor
                    yield obj

    def __truediv__(self, key):
        obj = self.__class__(
            archive_path=self.archive_path,
            cache_path=self.cache_path,
            member_path=self.member_path / key,
        )
        obj._descriptor = self._descriptor
        return obj
